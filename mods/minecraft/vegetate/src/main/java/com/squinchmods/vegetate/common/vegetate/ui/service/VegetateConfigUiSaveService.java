package com.squinchmods.vegetate.common.vegetate.ui.service;

import com.squinchmods.vegetate.common.vegetate.rules.VegetateConfigService;
import java.util.Objects;

public final class VegetateConfigUiSaveService implements ConfigUiSaveService {
  private final VegetateConfigService configService;
  private final VegetateConfigUiEditService editService;

  public VegetateConfigUiSaveService(
      VegetateConfigService configService, VegetateConfigUiEditService editService) {
    this.configService = Objects.requireNonNull(configService, "configService cannot be null");
    this.editService = Objects.requireNonNull(editService, "editService cannot be null");
  }

  @Override
  public ConfigUiApplyResult savePendingChanges() {
    editService.applyToConfig();
    configService.save();
    return ConfigUiApplyResult.success();
  }

  @Override
  public ConfigUiApplyResult discardPendingChanges() {
    editService.resetAll();
    return ConfigUiApplyResult.success();
  }

  @Override
  public ConfigUiApplyResult reloadFromSource() {
    configService.load();
    editService.resetAll();
    return ConfigUiApplyResult.success();
  }
}
