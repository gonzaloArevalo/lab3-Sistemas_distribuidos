# lab3-Sistemas_distribuidos

# Ejecutar los siguientes comandos para borrar contenedros viejos en caso de problemas
docker compose down -v
docker compose up --build

# Si se busca cambiar solo un contenedor
docker compose build NOMBRE_CONTENEDOR
docker compose up -d

# Detener contenedor
docker compose stop NOMBRE_CONTENEDOR

# Para ver replay, primero se debe detener publisher
docker compose exec audit python replay.py

# Para lo que son los scripts, si se esta utilizando linux se debe utilizar el siguiente comando primero
chmod +x run_load.sh run_burst.sh run_chaos.sh run_demo.sh replay.sh