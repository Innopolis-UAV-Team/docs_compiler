FROM python:3.10.9-slim-buster

WORKDIR /docs_compiler
COPY requirements.txt ./
RUN pip3 install -r requirements.txt

COPY . .