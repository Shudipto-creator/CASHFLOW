export default function Toast({ message }) {
  return message ? <div className="toast" role="status">{message}</div> : null
}
