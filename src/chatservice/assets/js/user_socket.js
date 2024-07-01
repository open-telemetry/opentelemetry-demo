import {Socket} from "phoenix"

let socket = new Socket("/socket", {params: {token: window.personToken}})
socket.connect()
export default socket
