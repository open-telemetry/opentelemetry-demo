#!/bin/bash
set -e

# Assuming "bundle exec ruby email_server.rb" is your Ruby command
bundle exec ruby email_server.rb &

# Assuming "./venv/bin/python3 memory-leak-3.py" is your Python command
./venv/bin/python3 memory-leak-3.py