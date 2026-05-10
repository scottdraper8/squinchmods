package com.squinchmods.vegetate.common.vegetate.ui.service;

public interface ConfigUiSaveService {
  ConfigUiApplyResult savePendingChanges();

  ConfigUiApplyResult discardPendingChanges();

  ConfigUiApplyResult reloadFromSource();
}
