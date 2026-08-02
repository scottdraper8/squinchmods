package org.squinchmods.investigate.rtf;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import raccoonman.reterraforged.world.worldgen.cell.Cell;
import raccoonman.reterraforged.world.worldgen.cell.heightmap.Levels;

final class ScanAccumulator {
    private static final double[] QUANTILES = {0.0, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 1.0};

    private final Levels levels;
    private final List<String> fields;
    private final List<Predicate> predicates;
    private final String rankField;
    private final boolean ascending;
    private final int topK;
    private final int exampleLimit;
    private final boolean retainGrid;
    private final Map<String, List<Double>> numeric = new LinkedHashMap<>();
    private final Map<String, Map<String, Long>> categorical = new LinkedHashMap<>();
    private final List<JsonObject> candidates = new ArrayList<>();
    private final List<JsonObject> examples = new ArrayList<>();
    private final List<JsonObject> grid = new ArrayList<>();
    private long inspected;
    private long matched;

    ScanAccumulator(Levels levels, JsonObject request, boolean retainGrid) {
        this.levels = levels;
        this.fields = strings(request.getAsJsonArray("fields"));
        this.predicates = predicates(request.getAsJsonArray("predicates"));
        this.rankField = request.get("rank_field").getAsString();
        this.ascending = request.get("ascending").getAsBoolean();
        this.topK = request.get("top_k").getAsInt();
        this.exampleLimit = request.get("example_limit").getAsInt();
        this.retainGrid = retainGrid;
    }

    void accept(Cell cell, double x, double z, int pixelX, int pixelZ) {
        Map<String, Object> values = new HashMap<>();
        for (String field : this.fields) {
            Object value = CellFields.value(cell, this.levels, field);
            values.put(field, value);
            if (value instanceof Number number) {
                this.numeric.computeIfAbsent(field, ignored -> new ArrayList<>())
                    .add(number.doubleValue());
            } else {
                this.categorical.computeIfAbsent(field, ignored -> new HashMap<>())
                    .merge(String.valueOf(value), 1L, Long::sum);
            }
        }
        this.inspected++;
        boolean matches = this.predicates.stream().allMatch(predicate -> predicate.test(values));
        JsonObject sample = sample(x, z, pixelX, pixelZ, values);
        if (matches) {
            this.matched++;
            if (this.examples.size() < this.exampleLimit) {
                this.examples.add(sample.deepCopy());
            }
            if (values.get(this.rankField) instanceof Number) {
                this.candidates.add(sample.deepCopy());
            }
        }
        if (this.retainGrid) {
            this.grid.add(sample);
        }
    }

    JsonObject finish() {
        if (this.inspected == 0) {
            throw new IllegalArgumentException("scan bounds and sample step selected no coordinates");
        }
        JsonObject result = new JsonObject();
        result.addProperty("inspected", this.inspected);
        result.addProperty("predicate_matches", this.matched);
        JsonObject summaries = new JsonObject();
        for (String field : this.fields) {
            if (this.numeric.containsKey(field)) {
                summaries.add(field, numericSummary(this.numeric.get(field)));
            } else {
                summaries.add(field, categoricalSummary(this.categorical.get(field)));
            }
        }
        result.add("fields", summaries);
        result.add("examples", array(this.examples));
        this.candidates.sort((left, right) -> {
            double a = left.get(this.rankField).getAsDouble();
            double b = right.get(this.rankField).getAsDouble();
            return this.ascending ? Double.compare(a, b) : Double.compare(b, a);
        });
        result.add("top_candidates", array(this.candidates.subList(
            0, Math.min(this.topK, this.candidates.size())
        )));
        return result;
    }

    List<JsonObject> grid() {
        return this.grid;
    }

    private JsonObject numericSummary(List<Double> source) {
        List<Double> values = new ArrayList<>(source);
        values.sort(Double::compare);
        JsonObject result = new JsonObject();
        result.addProperty("count", values.size());
        double sum = values.stream().mapToDouble(Double::doubleValue).sum();
        result.addProperty("min", values.getFirst());
        result.addProperty("max", values.getLast());
        result.addProperty("mean", sum / values.size());
        JsonObject quantiles = new JsonObject();
        for (double quantile : QUANTILES) {
            int index = (int) Math.round(quantile * (values.size() - 1));
            quantiles.addProperty(String.valueOf(quantile), values.get(index));
        }
        result.add("quantiles", quantiles);
        JsonArray histogram = new JsonArray();
        double min = values.getFirst();
        double max = values.getLast();
        int[] counts = new int[16];
        for (double value : values) {
            int bucket = max == min ? 0 : Math.min(15, (int) ((value - min) / (max - min) * 16));
            counts[bucket]++;
        }
        for (int index = 0; index < counts.length; index++) {
            JsonObject bucket = new JsonObject();
            bucket.addProperty("min", min + (max - min) * index / counts.length);
            bucket.addProperty("max", min + (max - min) * (index + 1) / counts.length);
            bucket.addProperty("count", counts[index]);
            histogram.add(bucket);
        }
        result.add("histogram", histogram);
        return result;
    }

    private JsonObject categoricalSummary(Map<String, Long> source) {
        JsonObject result = new JsonObject();
        result.addProperty("count", source.values().stream().mapToLong(Long::longValue).sum());
        JsonArray top = new JsonArray();
        source.entrySet().stream()
            .sorted(Map.Entry.<String, Long>comparingByValue(Comparator.reverseOrder())
                .thenComparing(Map.Entry.comparingByKey()))
            .limit(this.topK)
            .forEach(entry -> {
                JsonObject item = new JsonObject();
                item.addProperty("value", entry.getKey());
                item.addProperty("count", entry.getValue());
                top.add(item);
            });
        result.add("top", top);
        return result;
    }

    private static JsonObject sample(
        double x, double z, int pixelX, int pixelZ, Map<String, Object> values
    ) {
        JsonObject result = new JsonObject();
        result.addProperty("x", x);
        result.addProperty("z", z);
        result.addProperty("pixel_x", pixelX);
        result.addProperty("pixel_z", pixelZ);
        values.entrySet().stream().sorted(Map.Entry.comparingByKey()).forEach(entry -> {
            if (entry.getValue() instanceof Number number) {
                result.addProperty(entry.getKey(), number);
            } else {
                result.addProperty(entry.getKey(), String.valueOf(entry.getValue()));
            }
        });
        return result;
    }

    private static JsonArray array(List<JsonObject> values) {
        JsonArray result = new JsonArray();
        values.forEach(result::add);
        return result;
    }

    private static List<String> strings(JsonArray array) {
        List<String> result = new ArrayList<>();
        for (JsonElement element : array) {
            String field = element.getAsString();
            if (!CellFields.ALL.contains(field)) {
                throw new IllegalArgumentException("unknown requested field: " + field);
            }
            result.add(field);
        }
        return result;
    }

    private static List<Predicate> predicates(JsonArray array) {
        List<Predicate> result = new ArrayList<>();
        for (JsonElement element : array) {
            JsonObject value = element.getAsJsonObject();
            result.add(new Predicate(
                value.get("field").getAsString(), value.get("op").getAsString(),
                value.get("value").isJsonPrimitive()
                    && value.getAsJsonPrimitive("value").isNumber()
                    ? value.get("value").getAsDouble()
                    : value.get("value").getAsString()
            ));
        }
        return result;
    }

    private record Predicate(String field, String op, Object expected) {
        boolean test(Map<String, Object> values) {
            Object actual = values.get(this.field);
            if (actual == null) {
                throw new IllegalArgumentException("predicate field was not requested: " + this.field);
            }
            if (actual instanceof Number number && this.expected instanceof Number expectedNumber) {
                double left = number.doubleValue();
                double right = expectedNumber.doubleValue();
                return switch (this.op) {
                    case ">" -> left > right;
                    case ">=" -> left >= right;
                    case "<" -> left < right;
                    case "<=" -> left <= right;
                    case "==" -> left == right;
                    case "!=" -> left != right;
                    default -> throw new IllegalArgumentException("unknown numeric predicate op: " + this.op);
                };
            }
            return switch (this.op) {
                case "==" -> String.valueOf(actual).equals(String.valueOf(this.expected));
                case "!=" -> !String.valueOf(actual).equals(String.valueOf(this.expected));
                default -> throw new IllegalArgumentException("categorical predicate requires == or !=");
            };
        }
    }
}
