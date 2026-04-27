# Simulador Encicle CP 46007 Valencia

App de Streamlit para simular un mes operativo de reparto en el codigo postal 46007 de Valencia.

## Ejecutar

```powershell
streamlit run app.py
```

## Funcionamiento

- Usa portales reales de CartoCiudad filtrados al codigo postal 46007.
- Situa el microhub en el parking de la estacion Valencia Joaquin Sorolla.
- Optimiza una flota mensual con una heuristica ligera pensada para Render gratuito.
- Prioriza menos repartidores con jornadas mejor aprovechadas y horas trabajadas medidas en horas y minutos.
- Calcula el coste laboral sumando las horas reales trabajadas durante el mes.
- Modela un unico trabajador fijo en el hub.
- Permite calcular productividad por rango de paquetes/hora o por distancia, velocidad y tiempo de entrega.
- Permite editar velocidad media y preferencia 1-5 estrellas de cada vehiculo; la preferencia afecta a la optimizacion.
- Incluso en modo distancia se respeta el maximo de entregas/hora configurado por vehiculo.
- Las cargas en hub intentan llenar la capacidad operativa del vehiculo; la furgoneta separa inventario P/M y XL, y solo puede traspasar P/M si lo tiene cargado.
- Simula demanda, urgentes, estandares, incidencias, SLA, costes e ingresos.
- Permite activar o desactivar el aprovisionamiento por furgoneta nodriza.
- Genera tablas de pedidos con repartidor, vehiculo, hora, SLA, intento y origen de carga.
- Genera tablas de traspasos con hora, ubicacion, receptor y paquetes transferidos.
- Genera tabla de cargas en hub, evolucion por vehiculo y actividad por persona/hora.
- Exporta las tablas seleccionadas a un unico XLSX con una hoja por tabla.
- Muestra rutas por vehiculo sobre red viaria real OSM para el dia seleccionado, incluyendo las vueltas al hub cuando un vehiculo recarga.
- Marca en el mapa el hub, entregas, traspasos y cargas realizadas en el hub.
- Incluye capa WMS oficial de CartoCiudad para visualizar codigos postales.
- Calcula el Scorecard Encicle ponderado y exige el objetivo configurado.

La simulacion mensual usa aproximaciones rapidas de distancia. El mapa calcula rutas reales solo para el dia visible para reducir consumo de CPU.
