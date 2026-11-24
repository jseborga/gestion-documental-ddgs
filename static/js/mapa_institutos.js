// Mapa de institutos. Sin HTML armado con datos: los nombres se insertan como texto.
(function () {
  "use strict";
  var contenedor = document.getElementById("mapa");
  if (!contenedor || typeof L === "undefined") { return; }
  var colores = { rojo: "#c62828", ambar: "#f9a825", gris: "#757575", verde: "#2e7d32" };
  var mapa = L.map(contenedor, { preferCanvas: true }).setView([-16.5, -68.15], 7);
  var teselas = contenedor.dataset.teselas;
  if (teselas) {
    L.tileLayer(teselas, { maxZoom: 18, attribution: contenedor.dataset.atribucion || "" }).addTo(mapa);
  }

  function ventana(propiedades) {
    var div = document.createElement("div");
    var enlace = document.createElement("a");
    enlace.href = propiedades.url;
    enlace.textContent = (propiedades.numero ? propiedades.numero + ". " : "") + propiedades.nombre;
    var lugar = document.createElement("div");
    lugar.textContent = [propiedades.region, propiedades.provincia, propiedades.municipio]
      .filter(Boolean).join(" / ");
    div.appendChild(enlace);
    div.appendChild(lugar);
    if (propiedades.precision === "aproximada_localidad") {
      var aviso = document.createElement("em");
      aviso.textContent = "Ubicación aproximada";
      div.appendChild(aviso);
    }
    return div;
  }

  fetch(contenedor.dataset.geojson, { credentials: "same-origin", headers: { Accept: "application/json" } })
    .then(function (respuesta) {
      if (!respuesta.ok) { throw new Error("No se pudo cargar el mapa"); }
      return respuesta.json();
    })
    .then(function (datos) {
      var capa = L.geoJSON(datos, {
        pointToLayer: function (punto, latlng) {
          var aproximada = punto.properties.precision === "aproximada_localidad";
          return L.circleMarker(latlng, {
            radius: 8,
            color: colores[punto.properties.estado] || "#1f4e79",
            fillColor: colores[punto.properties.estado] || "#1f4e79",
            fillOpacity: aproximada ? 0.35 : 0.85,
            weight: 2,
            dashArray: aproximada ? "4 4" : null
          });
        },
        onEachFeature: function (punto, marcador) {
          marcador.bindPopup(ventana(punto.properties));
        }
      }).addTo(mapa);
      if (datos.features.length) { mapa.fitBounds(capa.getBounds(), { padding: [30, 30], maxZoom: 13 }); }
    })
    .catch(function (error) {
      var aviso = document.createElement("p");
      aviso.className = "mensaje error";
      aviso.textContent = error.message;
      contenedor.parentNode.insertBefore(aviso, contenedor);
    });
})();
