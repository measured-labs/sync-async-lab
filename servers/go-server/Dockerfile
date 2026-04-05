FROM golang:1.24 AS build
WORKDIR /app
COPY go.mod .
COPY main.go .
RUN CGO_ENABLED=0 go build -o server .

FROM gcr.io/distroless/static
WORKDIR /app
COPY --from=build /app/server .
CMD ["/app/server"]
