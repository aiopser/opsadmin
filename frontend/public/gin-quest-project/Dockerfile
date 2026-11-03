FROM golang:1.25-alpine AS build
WORKDIR /src
COPY . .
RUN go mod download && CGO_ENABLED=0 go build -tags=nomsgpack -trimpath -o /out/gin-quest .

FROM alpine:3.22
RUN adduser -D -u 10001 app && mkdir -p /data && chown app:app /data
COPY --from=build /out/gin-quest /usr/local/bin/gin-quest
USER app
WORKDIR /data
ENV ADDR=:8080 DB_PATH=/data/quest.db
EXPOSE 8080
ENTRYPOINT ["gin-quest"]
