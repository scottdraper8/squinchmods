package org.squinchmods.investigate.rtf;

import java.util.List;
import java.util.Set;

import raccoonman.reterraforged.world.worldgen.cell.Cell;
import raccoonman.reterraforged.world.worldgen.cell.heightmap.Levels;

final class CellFields {
    static final List<String> DEFAULTS = List.of(
        "height", "height_blocks", "terrain", "terrain_category",
        "continent_edge", "continent_distance", "river_mask", "river_zone",
        "temperature", "moisture", "erosion", "weirdness", "water_table",
        "terrain_region_id", "biome_region_id"
    );

    static final Set<String> ALL = Set.of(
        "height", "height_blocks", "height_erosion", "sediment", "gradient",
        "terrain", "terrain_category", "continent_id", "continent_edge",
        "continent_distance", "continent_x", "continent_z", "continent_scale",
        "river_mask", "river_water_level", "river_zone", "temperature", "moisture",
        "region_temperature", "region_moisture", "erosion", "terrain_erosion",
        "weirdness", "water_table", "terrain_region_id", "terrain_region_edge",
        "terrain_region_center_x", "terrain_region_center_z", "biome_region_id",
        "biome_region_edge", "macro_biome_id", "beach_noise"
    );

    private CellFields() {
    }

    static Object value(Cell cell, Levels levels, String field) {
        return switch (field) {
            case "height" -> cell.height;
            case "height_blocks" -> levels.scale(cell.height);
            case "height_erosion" -> cell.heightErosion;
            case "sediment" -> cell.sediment;
            case "gradient" -> cell.gradient;
            case "terrain" -> cell.terrain.getName();
            case "terrain_category" -> cell.terrain.getCategory().name();
            case "continent_id" -> cell.continentId;
            case "continent_edge" -> cell.continentEdge;
            case "continent_distance" -> cell.continentDistance;
            case "continent_x" -> cell.continentX;
            case "continent_z" -> cell.continentZ;
            case "continent_scale" -> cell.globalContinentScale;
            case "river_mask" -> cell.riverMask;
            case "river_water_level" -> cell.riverWaterLevel;
            case "river_zone" -> cell.riverZone.name();
            case "temperature" -> cell.temperature;
            case "moisture" -> cell.moisture;
            case "region_temperature" -> cell.regionTemperature;
            case "region_moisture" -> cell.regionMoisture;
            case "erosion" -> cell.erosion;
            case "terrain_erosion" -> cell.terrainErosion;
            case "weirdness" -> cell.weirdness;
            case "water_table" -> cell.waterTable;
            case "terrain_region_id" -> cell.terrainRegionId;
            case "terrain_region_edge" -> cell.terrainRegionEdge;
            case "terrain_region_center_x" -> cell.terrainRegionCenterX;
            case "terrain_region_center_z" -> cell.terrainRegionCenterZ;
            case "biome_region_id" -> cell.biomeRegionId;
            case "biome_region_edge" -> cell.biomeRegionEdge;
            case "macro_biome_id" -> cell.macroBiomeId;
            case "beach_noise" -> cell.beachNoise;
            default -> throw new IllegalArgumentException("unknown cell field: " + field);
        };
    }
}
