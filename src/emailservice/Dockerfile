FROM ruby:3.1.2-slim

RUN apt-get update -y && apt-get install -y build-essential

COPY Gemfile* ./

RUN bundle install

WORKDIR /email_server

COPY . .

EXPOSE ${EMAIL_SERVICE_PORT}
ENTRYPOINT ["bundle", "exec", "ruby", "email_server.rb"]
