-- BhumiSetu Database Initialization: Ensure PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Log verification outputs
SELECT version();
SELECT PostGIS_Full_Version();
