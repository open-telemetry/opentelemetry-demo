import socket from "./user_socket.js";

const form = document.getElementById('login-form');
const loginContainer = document.getElementById('login-container');
const chatContainer = document.getElementById('chat-container');
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const nameInput = document.getElementById('name-input');

let chatInputEventHandler;
let channelEventHandler;

const addEventHandlers = (channel) => {
  removeEventHandlers(channel);

  chatInputEventHandler = (event) => {
    if (event.key === 'Enter') {
      const message = chatInput.value.trim();
      if (message) {
        sendMessage(channel, nameInput.value, message);
        chatInput.value = '';
      }
    }
  };
  chatInput.addEventListener('keydown', chatInputEventHandler);

  channelEventHandler = (payload) => {
    renderMessage(payload);
  };
  channel.on('shout', channelEventHandler);
};

const removeEventHandlers = (channel) => {
  if (chatInputEventHandler) {
    chatInput.removeEventListener('keydown', chatInputEventHandler);
    chatInputEventHandler = null;
  }

  if (channelEventHandler) {
    channel.off('shout', channelEventHandler);
    channelEventHandler = null;
  }
};

form.addEventListener('submit', (event) => {
  event.preventDefault();

  const name = nameInput.value;

  // Sanitize the username
  const sanitizedName = name.replace(/[^a-zA-Z0-9]/g, '');
  const urlParams = new URLSearchParams(window.location.search);
  const channelName = urlParams.get('channel') || sanitizedName;
  console.log(channelName);
  const channel = socket.channel(`chat:${channelName}`, {});
  channel.join()
    .receive("ok", resp => {
      console.log("Joined successfully", resp);

      // Hide the login form and show the chat window
      loginContainer.style.display = 'none';
      chatContainer.style.display = 'block';

      addEventHandlers(channel);
    })
    .receive("error", resp => {
      console.log("Unable to join", resp);
    });
});

function sendMessage(channel, name, message) {
  channel.push('shout', {
    name: name,
    message: message,
    inserted_at: new Date()
  })
}

function renderMessage(payload) {
  console.log(payload)
}

