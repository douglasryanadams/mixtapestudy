FROM python:3.11.10-alpine

ENV VIRTUAL_ENV=/home/app/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --upgrade pip
RUN apk add curl build-base libpq libpq-dev

RUN adduser -D nonroot
RUN mkdir /home/app/ && chown -R nonroot:nonroot /home/app
RUN mkdir /home/app/log
WORKDIR /home/app
USER nonroot

COPY --chown=nonroot:nonroot requirements.txt .
RUN python -m venv $VIRTUAL_ENV
RUN pip install -r requirements.txt

COPY --chown=nonroot:nonroot alembic.ini .
COPY --chown=nonroot:nonroot alembic alembic
COPY --chown=nonroot:nonroot mixtapestudy mixtapestudy

CMD ["gunicorn", "-w 4", "-t 30", "-b 0.0.0.0", "mixtapestudy.app:create_app()"]
