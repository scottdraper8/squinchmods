package com.squinchmods.vegetate.common.vegetate.rules.serialization;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.squinchmods.vegetate.common.vegetate.rules.VegetateConfig;
import com.squinchmods.vegetate.common.vegetate.rules.VegetationFeatureRule;
import java.util.Map;

public class VegetateConfigSerializer {

  private static final String GENERAL = "general";
  private static final String DISABLE_ALL_MUSHROOMS = "disable_all_mushrooms";
  private static final String FEATURES = "features";
  private static final String NAME = "name";
  private static final String CATEGORY = "category";
  private static final String ENABLED = "enabled";

  public static JsonObject serialize(VegetateConfig config, boolean saveOnlyChanged) {
    JsonObject json = new JsonObject();

    JsonObject general = new JsonObject();
    general.addProperty(DISABLE_ALL_MUSHROOMS, config.disableAllMushrooms);
    json.add(GENERAL, general);

    JsonArray features = new JsonArray();
    for (Map.Entry<String, VegetationFeatureRule> entry : config.getFeatureRules().entrySet()) {
      if (!saveOnlyChanged || !entry.getValue().isUsingDefaultValues()) {
        JsonObject featureJson = new JsonObject();
        featureJson.addProperty(NAME, entry.getKey());
        featureJson.addProperty(CATEGORY, entry.getValue().getCategory());
        featureJson.addProperty(ENABLED, entry.getValue().isEnabled());
        features.add(featureJson);
      }
    }
    json.add(FEATURES, features);

    return json;
  }

  public static void deserialize(JsonObject json, VegetateConfig config) {
    if (json.has(GENERAL)) {
      JsonObject general = json.getAsJsonObject(GENERAL);
      if (general.has(DISABLE_ALL_MUSHROOMS)) {
        config.disableAllMushrooms = general.get(DISABLE_ALL_MUSHROOMS).getAsBoolean();
      }
    }

    if (json.has(FEATURES)) {
      JsonArray features = json.getAsJsonArray(FEATURES);
      for (JsonElement element : features) {
        JsonObject featureJson = element.getAsJsonObject();
        if (featureJson.has(NAME)) {
          String name = featureJson.get(NAME).getAsString();
          String category =
              featureJson.has(CATEGORY) ? featureJson.get(CATEGORY).getAsString() : "unknown";

          VegetationFeatureRule rule =
              config
                  .getFeatureRules()
                  .computeIfAbsent(name, ignored -> new VegetationFeatureRule(category));

          if (featureJson.has(ENABLED)) {
            rule.setEnabled(featureJson.get(ENABLED).getAsBoolean());
          }
        }
      }
    }
  }
}
