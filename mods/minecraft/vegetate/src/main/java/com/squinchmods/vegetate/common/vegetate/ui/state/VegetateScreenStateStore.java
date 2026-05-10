package com.squinchmods.vegetate.common.vegetate.ui.state;

import dev.isxander.yacl3.gui.YACLScreen;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

public final class VegetateScreenStateStore {
  private final Map<String, VegetateScreenState> states = new HashMap<>();

  public void save(YACLScreen screen) {
    String screenKey = screenKey(screen);
    VegetateYaclStateAccess.capture(screen).ifPresent(state -> this.states.put(screenKey, state));
  }

  public void restore(YACLScreen screen) {
    get(screenKey(screen)).ifPresent(state -> VegetateYaclStateAccess.restore(screen, state));
  }

  public void clear() {
    this.states.clear();
  }

  public Optional<VegetateScreenState> get(String screenKey) {
    return Optional.ofNullable(this.states.get(screenKey));
  }

  private static String screenKey(YACLScreen screen) {
    return screen.getTitle().getString();
  }
}
