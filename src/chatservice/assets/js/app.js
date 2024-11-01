// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
// Copyright 2021 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

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
  console.log("form submitted");
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
  console.log(payload);
  const messageContainer = document.createElement('div');
  messageContainer.classList.add('message');

  const nameElement = document.createElement('span');
  nameElement.classList.add('name');
  nameElement.textContent = payload.name;

  const messageElement = document.createElement('p');
  messageElement.textContent = payload.message;

  const timestampElement = document.createElement('small');
  timestampElement.classList.add('timestamp');
  timestampElement.textContent = new Date(payload.inserted_at).toLocaleString();

  messageContainer.appendChild(nameElement);
  messageContainer.appendChild(messageElement);
  messageContainer.appendChild(timestampElement);

  chatMessages.appendChild(messageContainer);
}

