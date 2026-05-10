package com.squinchmods.vegetate.common.vegetate.rules;

import java.util.Map;
import java.util.TreeMap;

public class VegetateConfig {

  public boolean disableAllMushrooms = false;

  private final Map<String, VegetationFeatureRule> featureRules = new TreeMap<>();

  public VegetateConfig() {}

  public Map<String, VegetationFeatureRule> getFeatureRules() {
    return featureRules;
  }
}
