FROM python:3.12.6-alpine

ENV VIRTUAL_ENV=/home/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --upgrade pip
RUN apk add curl

RUN adduser -D nonroot
RUN mkdir /home/app/ && chown -R nonroot:nonroot /home/app
#RUN mkdir -p /var/log/flask-app && touch /var/log/flask-app/flask-app.err.log && touch /var/log/flask-app/flask-app.out.log
#RUN chown -R nonroot:nonroot /var/log/flask-app
WORKDIR /home/app
USER nonroot

COPY --chown=nonroot:nonroot requirements.txt .
RUN python -m venv $VIRTUAL_ENV
RUN pip install -r requirements.txt

COPY --chown=nonroot:nonroot mixtapestudy mixtapestudy

CMD ["gunicorn", "-w 4", "-t 30", "-b 0.0.0.0", "mixtapestudy.app:create_app()"]
