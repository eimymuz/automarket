-- Ejecutar como superusuario "postgres".
-- Crea un usuario propio para la aplicación (nunca usar "postgres" desde la API).
CREATE ROLE automarket_app WITH LOGIN PASSWORD 'CAMBIA_ESTA_CLAVE';
CREATE DATABASE automarket OWNER automarket_app ENCODING 'UTF8' TEMPLATE template0;
\connect automarket
ALTER SCHEMA public OWNER TO automarket_app;
