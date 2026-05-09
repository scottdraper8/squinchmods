package com.squinchmods.treeify.common.treeify.ui.service;

import com.squinchmods.treeify.common.treeify.rules.TreeifyConfigService;
import java.util.Objects;

public final class TreeifyConfigUiSaveService implements ConfigUiSaveService {
    private final TreeifyConfigService configService;
    private final TreeifyConfigUiEditService editService;

    public TreeifyConfigUiSaveService(TreeifyConfigService configService, TreeifyConfigUiEditService editService) {
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
