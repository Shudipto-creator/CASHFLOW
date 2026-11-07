"""Live check of the FINN CFO chat: English, Chinese, follow-ups, out of scope.

Runs against the local Ollama model configured in ``app/.env`` (default
``llama3.2``).  It uses a temporary application database, so it never writes to
``data/cfone.db``, and it only reads the FINNDB sandbox.

Usage (from the repository root):

    python scripts/verify_cfo_llm.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# The check prints Chinese answers; the default Windows console code page cannot
# encode them and would abort the run before the remaining cases execute.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.routers import banking_agent
from app.services import finn_bank


CASES = [
    ("English balance", "What is my balance?"),
    ("English out-of-context", "Can you recommend the best pizza in Rome?"),
    ("Chinese balance", "我的账户余额是多少？"),
    ("Chinese out-of-context", "给我推荐一部好看的电影。"),
    ("English spending", "How much did I spend this month?"),
    ("English follow-up", "and last month?"),
    ("Chinese spending", "我这个月花了多少钱？"),
    ("Chinese follow-up", "上个月呢？"),
]


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        engine = create_engine(
            f"sqlite:///{Path(tmp) / 'app.db'}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        db = Session()

        try:
            finn_bank.SessionLocal = Session
            finn_bank.DB_PATH = Path("data/finndb.sqlite").resolve()

            user = models.User(
                email="live-check@example.com",
                password_hash="x",
                company_name="Li Wei",
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            conversation_id = "live-llm-check"
            for label, message in CASES:
                response = await banking_agent.agent_chat(
                    banking_agent.AgentChatRequest(
                        message=message,
                        conversation_id=conversation_id,
                        processing_mode="local",
                    ),
                    user,
                    db,
                )
                print(f"\n[{label}] {message}")
                print(
                    f"  code={response.code} language={response.language} "
                    f"operation={response.operation_id}"
                )
                print(f"  {response.message}")

            history = await banking_agent.get_agent_chat_history(
                conversation_id, 200, user, db
            )
            print(f"\nStored turns: {len(history['messages'])}")
            assert len(history["messages"]) == len(CASES) * 2

            # A context-dependent conversation turn: the interpreter must see
            # what was said before, not just this sentence.
            context_turn = await banking_agent.agent_chat(
                banking_agent.AgentChatRequest(
                    message="I run a small bakery in Shanghai.",
                    conversation_id=conversation_id,
                    processing_mode="local",
                ),
                user,
                db,
            )
            follow_up = await banking_agent.agent_chat(
                banking_agent.AgentChatRequest(
                    message="What can you help me with?",
                    conversation_id=conversation_id,
                    processing_mode="local",
                ),
                user,
                db,
            )
            print("\n[Context turn] I run a small bakery in Shanghai.")
            print(f"  code={context_turn.code} language={context_turn.language}")
            print(f"  {context_turn.message}")
            print("\n[Context follow-up] What can you help me with?")
            print(f"  code={follow_up.code} language={follow_up.language}")
            print(f"  {follow_up.message}")

            final_history = await banking_agent.get_agent_chat_history(
                conversation_id, 200, user, db
            )
            assert len(final_history["messages"]) == (len(CASES) + 2) * 2
            print(f"\nFinal stored turns: {len(final_history['messages'])}")
        finally:
            db.close()
            engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
