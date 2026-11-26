# Reenvío TCP dentro de la red de Docker hacia el SeaweedFS del proyecto.
# Motivo: boto3 rechaza nombres de host con guion bajo (p. ej. "estudio_seaweedfs"),
# que es el formato de nombres internos de EasyPanel. La app se conecta a
# http://s3-proxy:8333 y socat reenvía cada conexión a S3_SERVICIO_INTERNO.
FROM alpine:3.22
RUN apk add --no-cache socat
USER nobody
EXPOSE 8333
ENTRYPOINT ["/bin/sh", "-c", "exec socat TCP-LISTEN:8333,fork,reuseaddr TCP:${S3_SERVICIO_INTERNO:?Defina S3_SERVICIO_INTERNO}"]
