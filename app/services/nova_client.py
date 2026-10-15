"""AWS Bedrock Nova client wrapper"""

import boto3
import json
import time
import logging
import base64
import re
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class NovaClient:
    """Wrapper for AWS Bedrock API interactions"""

    def __init__(self):
        """Initialize AWS Bedrock client"""
        try:
            client_kwargs = {
                "region_name": settings.aws_region,
            }

            # Only set explicit credentials when both key and secret are provided.
            # Otherwise boto3's default credential chain is used.
            if settings.aws_access_key_id and settings.aws_secret_access_key:
                client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
                client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
                if settings.aws_session_token:
                    client_kwargs["aws_session_token"] = settings.aws_session_token

            self.client = boto3.client("bedrock-runtime", **client_kwargs)
            self.model_id = settings.nova_lite_model_id or "global.amazon.nova-2-lite-v1:0"
            self.sonic_model_id = settings.nova_sonic_model_id or "global.amazon.nova-2-sonic-v1:0"
            self.embedding_model_id = settings.embedding_model_id
            logger.info(f"AWS Bedrock client initialized successfully (model={self.model_id})")
        except Exception as e:
            logger.error(f"Failed to initialize AWS Bedrock client: {str(e)}")
            raise

    @staticmethod
    def _profile_model_candidates(model_id: str) -> List[str]:
        """Return candidate inference-profile model IDs for a given model ID."""
        candidates = [model_id]
        if model_id.startswith("amazon."):
            candidates.append(f"global.{model_id}")
        return candidates

    @staticmethod
    def _parse_json_response(response_text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from raw model output, including markdown-fenced JSON."""
        candidates = []
        text = (response_text or "").strip()
        if not text:
            return None

        # Candidate 1: full text as-is.
        candidates.append(text)

        # Candidate 2+: markdown-fenced blocks.
        if "```" in text:
            parts = text.split("```")
            for idx in range(1, len(parts), 2):
                block = parts[idx].strip()
                if block.lower().startswith("json"):
                    block = block.split("\n", 1)[1].strip() if "\n" in block else ""
                if block:
                    candidates.append(block)

        # Candidate N: broad brace extraction.
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidates.append(text[first_brace : last_brace + 1].strip())

        decoder = json.JSONDecoder()

        def try_load_json(raw: str) -> Optional[Dict[str, Any]]:
            raw = raw.strip()
            if not raw:
                return None

            # Attempt strict JSON first.
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

            # Attempt extracting first JSON object from mixed prose.
            for idx, ch in enumerate(raw):
                if ch != "{":
                    continue
                try:
                    parsed, _ = decoder.raw_decode(raw[idx:])
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    continue

            # Normalize common model JSON quirks and retry.
            normalized = raw
            normalized = normalized.replace("\u201c", '"').replace("\u201d", '"')
            normalized = normalized.replace("\u2018", "'").replace("\u2019", "'")
            normalized = re.sub(r",\s*([}\]])", r"\1", normalized)  # remove trailing commas
            normalized = re.sub(r"\bTrue\b", "true", normalized)
            normalized = re.sub(r"\bFalse\b", "false", normalized)
            normalized = re.sub(r"\bNone\b", "null", normalized)

            try:
                parsed = json.loads(normalized)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return None

            return None

        seen = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            parsed = try_load_json(candidate)
            if parsed is not None:
                return parsed

        return None

    def invoke_agent(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        reasoning_effort: str = "medium",
    ) -> Dict[str, Any]:
        """
        Invoke Nova model with given parameters

        Args:
            prompt: User/agent prompt text
            system_prompt: System instructions for agent behavior
            temperature: 0.0-1.0, controls randomness
            max_tokens: Maximum response length
            reasoning_effort: "low", "medium", or "high"

        Returns:
            Parsed JSON response from model
        """
        model_candidates = self._profile_model_candidates(self.model_id)
        for attempt in range(settings.max_retries):
            try:
                logger.info(f"Invoking Nova model (attempt {attempt + 1}/{settings.max_retries})")

                # Invoke model via converse API
                last_client_error = None
                response = None
                selected_model_id = None
                for candidate in model_candidates:
                    selected_model_id = candidate
                    try:
                        response = self.client.converse(
                            modelId=candidate,
                            messages=[{"role": "user", "content": [{"text": prompt}]}],
                            system=[{"text": system_prompt}],
                            inferenceConfig={
                                "temperature": temperature,
                                "maxTokens": max_tokens,
                            },
                        )
                        break
                    except ClientError as candidate_error:
                        last_client_error = candidate_error
                        error_code = candidate_error.response.get("Error", {}).get("Code", "")
                        error_message = candidate_error.response.get("Error", {}).get("Message", "")

                        # When on-demand model IDs are rejected, try inference-profile candidate.
                        if (
                            error_code == "ValidationException"
                            and "on-demand throughput" in error_message.lower()
                            and candidate != model_candidates[-1]
                        ):
                            logger.warning(
                                "Model ID %s rejected for on-demand throughput; retrying with inference-profile ID.",
                                candidate,
                            )
                            continue
                        raise

                if response is None and last_client_error is not None:
                    raise last_client_error

                if selected_model_id and selected_model_id != self.model_id:
                    self.model_id = selected_model_id
                    logger.info("Switched Nova model ID to %s", self.model_id)

                # Extract response text from converse API response
                content_blocks = response["output"]["message"]["content"]
                response_text = "".join(
                    block["text"] for block in content_blocks if "text" in block
                )

                logger.info(f"Nova model invoked successfully")

                # Try to parse as JSON (including markdown-fenced JSON)
                parsed_response = self._parse_json_response(response_text)
                if parsed_response is not None:
                    return parsed_response

                # If not JSON, return as text in a dict
                logger.warning("Response is not valid JSON, returning as text")
                return {"response": response_text, "raw_text": True}

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                error_message = e.response.get("Error", {}).get("Message", str(e))

                logger.error(f"AWS Bedrock error (attempt {attempt + 1}): {error_code} - {error_message}")

                # Check if we should retry
                if attempt < settings.max_retries - 1:
                    if error_code in ["ThrottlingException", "ServiceUnavailableException"]:
                        # Exponential backoff
                        wait_time = (2**attempt) * 1
                        logger.info(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue

                # Return error response
                return {"error": f"{error_code}: {error_message}"}

            except Exception as e:
                logger.error(f"Unexpected error invoking Nova model: {str(e)}")

                if attempt < settings.max_retries - 1:
                    wait_time = (2**attempt) * 1
                    time.sleep(wait_time)
                    continue

                return {"error": f"Failed to invoke model: {str(e)}"}

        return {"error": "Max retries exceeded"}

    def generate_embeddings(self, text: str) -> List[float]:
        """
        Generate vector embeddings for text using Titan Embed Text model

        Args:
            text: Text to embed

        Returns:
            1024-dimensional embedding vector
        """
        try:
            # Truncate text if too long
            if len(text) > 8000:
                text = text[:8000]

            # Titan Embed Text API format
            request_body = {
                "inputText": text
            }

            response = self.client.invoke_model(
                modelId=self.embedding_model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(request_body),
            )

            response_body = json.loads(response["body"].read())
            # Titan returns embedding in this structure
            embedding = response_body.get("embedding", [])

            if embedding:
                logger.info(f"Generated embedding with {len(embedding)} dimensions")
            else:
                logger.warning(f"No embedding returned from model")
            
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {str(e)}")
            return []

    def check_connection(self) -> bool:
        """
        Check if AWS Bedrock connection is working

        Returns:
            True if connected, False otherwise
        """
        try:
            # Try a simple embedding generation
            test_embedding = self.generate_embeddings("test connection")
            return len(test_embedding) > 0
        except:
            return False

    def synthesize_speech_with_sonic(
        self,
        text: str,
        voice_id: str = "Matthew",
        audio_format: str = "mp3",
    ) -> Dict[str, Any]:
        """
        Synthesize speech from text using Nova Sonic.

        Returns:
            {"audio_base64": "...", "mime_type": "audio/mpeg"}
            or {"error": "..."}
        """
        if not text or not text.strip():
            return {"error": "Cannot synthesize empty text"}

        text = text.strip()
        if len(text) > 3500:
            text = text[:3500]

        payload_variants = [
            {
                "inputText": text,
                "audioGenerationConfig": {
                    "voiceId": voice_id,
                    "audioFormat": audio_format,
                },
            },
            {
                "messages": [{"role": "user", "content": [{"text": text}]}],
                "outputModalities": ["AUDIO"],
                "audioConfig": {
                    "voiceId": voice_id,
                    "format": audio_format,
                },
            },
            {
                "input": {"text": text},
                "speech": {
                    "voiceId": voice_id,
                    "format": audio_format,
                },
            },
        ]

        for idx, payload in enumerate(payload_variants):
            try:
                # Variant 1: try receiving binary audio directly.
                response = self.client.invoke_model(
                    modelId=self.sonic_model_id,
                    contentType="application/json",
                    accept="audio/mpeg" if audio_format.lower() == "mp3" else "application/octet-stream",
                    body=json.dumps(payload),
                )
                raw_audio = response["body"].read()
                if raw_audio:
                    return {
                        "audio_base64": base64.b64encode(raw_audio).decode("utf-8"),
                        "mime_type": "audio/mpeg" if audio_format.lower() == "mp3" else "audio/wav",
                    }
            except Exception as direct_audio_exc:
                logger.warning(
                    "Nova Sonic direct audio attempt %s failed: %s",
                    idx + 1,
                    str(direct_audio_exc),
                )

            try:
                # Variant 2: try receiving JSON with audio payload in body.
                response = self.client.invoke_model(
                    modelId=self.sonic_model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps(payload),
                )
                response_body = json.loads(response["body"].read())
                audio_base64 = (
                    response_body.get("audio")
                    or response_body.get("audioBase64")
                    or response_body.get("output", {}).get("audio")
                    or response_body.get("outputAudio")
                )
                if audio_base64:
                    return {
                        "audio_base64": audio_base64,
                        "mime_type": "audio/mpeg" if audio_format.lower() == "mp3" else "audio/wav",
                    }
            except Exception as json_audio_exc:
                logger.warning(
                    "Nova Sonic JSON audio attempt %s failed: %s",
                    idx + 1,
                    str(json_audio_exc),
                )

        return {
            "error": "Nova Sonic speech synthesis failed for all supported request formats",
        }
