package com.squinchmods.treeify.common.treeify.ui.service;

public interface ConfigUiSaveService
{
	ConfigUiApplyResult savePendingChanges();

	ConfigUiApplyResult discardPendingChanges();

	ConfigUiApplyResult reloadFromSource();
}
