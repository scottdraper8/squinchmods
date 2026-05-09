package com.squinchmods.treeify.common.treeify.ui.service;

import com.squinchmods.treeify.common.treeify.ui.model.ConfigUiEntryId;

public interface ConfigUiEditService
{
	boolean isEnabled(ConfigUiEntryId entryId);
	void setEnabled(ConfigUiEntryId entryId, boolean enabled);

	float getDensityMultiplier(ConfigUiEntryId entryId);
	void setDensityMultiplier(ConfigUiEntryId entryId, float densityMultiplier);

	int getHeightDelta(ConfigUiEntryId entryId);
	void setHeightDelta(ConfigUiEntryId entryId, int heightDelta);

	boolean getDisableAllTrees();
	void setDisableAllTrees(boolean value);

	boolean getDisableAllMushrooms();
	void setDisableAllMushrooms(boolean value);

	float getGlobalTreeDensityMultiplier();
	void setGlobalTreeDensityMultiplier(float value);

	float getGlobalMushroomDensityMultiplier();
	void setGlobalMushroomDensityMultiplier(float value);

	boolean hasUnsavedChanges(ConfigUiEntryId entryId);

	void reset(ConfigUiEntryId entryId);
	void resetAll();
}
