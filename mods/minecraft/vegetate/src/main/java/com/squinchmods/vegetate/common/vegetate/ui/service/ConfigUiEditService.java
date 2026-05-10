package com.squinchmods.vegetate.common.vegetate.ui.service;

import com.squinchmods.vegetate.common.vegetate.ui.model.ConfigUiEntryId;

public interface ConfigUiEditService {
  boolean isEnabled(ConfigUiEntryId entryId);

  void setEnabled(ConfigUiEntryId entryId, boolean enabled);

  boolean getDisableAllMushrooms();

  void setDisableAllMushrooms(boolean value);

  boolean hasUnsavedChanges(ConfigUiEntryId entryId);

  void reset(ConfigUiEntryId entryId);

  void resetAll();
}
