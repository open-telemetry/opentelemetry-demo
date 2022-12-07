FROM ruby:3.1.2-slim

RUN apt-get update -y && apt-get install -y build-essential

WORKDIR /email_server

COPY . .

RUN bundle install
RUN chmod 666 ./Gemfile.lock

EXPOSE ${EMAIL_SERVICE_PORT}
ENTRYPOINT ["bundle", "exec", "ruby", "email_server.rb"]
