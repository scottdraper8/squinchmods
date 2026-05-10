package com.squinchmods.vegetate.common.vegetate.ui.state;

import com.squinchmods.vegetate.common.vegetate.ui.service.VegetateConfigSession;
import dev.isxander.yacl3.gui.YACLScreen;
import java.util.Map;

public final class VegetateConfigSessionImpl implements VegetateConfigSession {
  private final VegetateScreenStateStore stateStore = new VegetateScreenStateStore();
  private String currentTabId = "";

  @Override
  public String currentTabId() {
    return currentTabId;
  }

  @Override
  public void setCurrentTabId(String tabId) {
    this.currentTabId = tabId;
  }

  @Override
  public String getSearchText(String screenId) {
    return stateStore.get(screenId).map(VegetateScreenState::lastSearchText).orElse("");
  }

  @Override
  public void setSearchText(String screenId, String searchText) {
    // Handled via capture in saveFrom
  }

  @Override
  public double getScrollAmount(String screenId) {
    return stateStore.get(screenId).map(VegetateScreenState::lastScrollAmount).orElse(0.0);
  }

  @Override
  public void setScrollAmount(String screenId, double scrollAmount) {
    // Handled via capture in saveFrom
  }

  @Override
  public Map<String, Boolean> getCollapsedGroups(String screenId) {
    return stateStore.get(screenId).map(VegetateScreenState::collapsedGroups).orElse(Map.of());
  }

  @Override
  public void setCollapsedGroups(String screenId, Map<String, Boolean> collapsedGroups) {
    // Handled via capture in saveFrom
  }

  @Override
  public void saveFrom(YACLScreen screen) {
    stateStore.save(screen);
  }

  @Override
  public void loadInto(YACLScreen screen) {
    stateStore.restore(screen);
  }
}
