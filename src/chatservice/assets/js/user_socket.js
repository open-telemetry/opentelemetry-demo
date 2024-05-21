import {Socket} from "phoenix"

export function joinChannel(channel, params, onSuccess, onError) {
  const socket = new Socket("/socket", { params: {
    name: params.name,
    session_id: params.session_id
  }})
  socket.connect()

  channel = socket.channel("chat:lobby", {})
  channel.join()
    .receive("ok", resp => { (onSuccess) ? onSuccess(resp) : false })
    .receive("error", resp => { (onError) ? onError(resp) : false })
}
