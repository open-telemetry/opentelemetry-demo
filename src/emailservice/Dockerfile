FROM ruby:3.1.2-slim

RUN apt-get update -y && apt-get install -y build-essential

RUN addgroup --system mygroup
RUN adduser --system --shell /sbin/nologin --ingroup mygroup myuser

WORKDIR /email_server

RUN chown myuser:mygroup /email_server

USER myuser

COPY --chown=myuser:mygroup . .

RUN bundle install
RUN chmod 666 ./Gemfile.lock

EXPOSE ${EMAIL_SERVICE_PORT}
ENTRYPOINT ["bundle", "exec", "ruby", "email_server.rb"]
