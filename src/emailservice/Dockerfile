FROM ruby:3.1.2-slim as base

FROM base as builder

WORKDIR /tmp

COPY Gemfile Gemfile.lock .

# RUN apt-get update -y && apt-get install --no-install-recommends -y build-base && rm -rf /var/lib/apt/lists/* 
RUN apt-get update -y && apt-get install --no-install-recommends -y make gcc && bundle install


FROM base as release

WORKDIR /email_server

COPY . .

RUN chmod 666 ./Gemfile.lock

COPY --from=builder /usr/local/bundle/ /usr/local/bundle/


EXPOSE ${EMAIL_SERVICE_PORT}
ENTRYPOINT ["bundle", "exec", "ruby", "email_server.rb"]
