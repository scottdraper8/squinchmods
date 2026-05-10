package com.squinchmods.vegetate.common.vegetate.ui.state;

import java.util.Map;

public record VegetateScreenState(
    String lastSearchText, double lastScrollAmount, Map<String, Boolean> collapsedGroups) {
  public VegetateScreenState {
    lastSearchText = lastSearchText == null ? "" : lastSearchText;
    collapsedGroups = collapsedGroups == null ? Map.of() : Map.copyOf(collapsedGroups);
  }
}
