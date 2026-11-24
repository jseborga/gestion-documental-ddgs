// En la ficha: un clic en el mapa llena las coordenadas del formulario de ubicación.
(function () {
  "use strict";
  var contenedor = document.getElementById("mapa-ficha");
  var campo = document.getElementById("id_coordenadas");
  var precision = document.getElementById("id_precision");
  if (!contenedor || !campo || typeof L === "undefined") { return; }
  if (!contenedor.dataset.teselas) { contenedor.hidden = true; return; }
  var lat = parseFloat(contenedor.dataset.lat);
  var lon = parseFloat(contenedor.dataset.lon);
  var tiene = !isNaN(lat) && !isNaN(lon);
  var mapa = L.map(contenedor).setView(tiene ? [lat, lon] : [-16.5, -68.15], tiene ? 15 : 7);
  L.tileLayer(contenedor.dataset.teselas, { maxZoom: 19 }).addTo(mapa);
  var marcador = tiene ? L.marker([lat, lon]).addTo(mapa) : null;
  mapa.on("click", function (evento) {
    var punto = evento.latlng;
    if (marcador) { marcador.setLatLng(punto); } else { marcador = L.marker(punto).addTo(mapa); }
    campo.value = punto.lat.toFixed(6) + ", " + punto.lng.toFixed(6);
    if (precision) { precision.value = "verificada_mapa"; }
  });
})();
