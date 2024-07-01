import socket from "./user_socket.js"

const name    = document.getElementById("name")
const message = document.getElementById("message")
const send    = document.getElementById("message-submit")

channel = socket.channel("chat:"+42, {}) 
channel.join()
  .receive("ok", resp => { console.log("success") })
  .receive("error", resp => { console.error(resp) })
channel.on('shout', renderMessage)

send.addEventListener("click", function(event) {
  sendMessage(message.value)
  message.value = ""
})

function sendMessage(message) {
  channel.push('shout', {
    name: name.value || "guest",
    message: message,
    inserted_at: new Date()
  })
}

function renderMessage(payload) {
  console.log(payload)
}
