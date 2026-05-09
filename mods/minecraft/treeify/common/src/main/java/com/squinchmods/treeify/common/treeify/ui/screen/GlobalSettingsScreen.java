package com.squinchmods.treeify.common.treeify.ui.screen;

import com.squinchmods.treeify.common.treeify.ui.service.ConfigUiEditService;
import com.squinchmods.treeify.common.treeify.ui.shell.TreeifyConfigScreenContext;
import com.squinchmods.treeify.common.treeify.ui.shell.TreeifyConfigTabComposer;
import dev.isxander.yacl3.api.ConfigCategory;
import dev.isxander.yacl3.api.Option;
import dev.isxander.yacl3.api.OptionDescription;
import dev.isxander.yacl3.api.OptionGroup;
import dev.isxander.yacl3.api.YetAnotherConfigLib;
import dev.isxander.yacl3.api.controller.BooleanControllerBuilder;
import dev.isxander.yacl3.api.controller.FloatSliderControllerBuilder;
import net.minecraft.network.chat.Component;

public class GlobalSettingsScreen implements TreeifyConfigTabComposer {

    private final ConfigUiEditService editService;

    public GlobalSettingsScreen(ConfigUiEditService editService) {
        this.editService = editService;
    }

    @Override
    public void compose(YetAnotherConfigLib.Builder builder, TreeifyConfigScreenContext context) {
        ConfigCategory.Builder categoryBuilder = ConfigCategory.createBuilder()
                .name(Component.translatable("treeify.gui.category.global"));

        OptionGroup.Builder killSwitchGroup = OptionGroup.createBuilder()
                .name(Component.translatable("treeify.gui.group.kill_switches"));

        killSwitchGroup.option(Option.<Boolean>createBuilder()
                .name(Component.translatable("treeify.gui.option.disable_all_trees"))
                .binding(
                        false,
                        editService::getDisableAllTrees,
                        editService::setDisableAllTrees
                )
                .controller(BooleanControllerBuilder::create)
                .build());

        killSwitchGroup.option(Option.<Boolean>createBuilder()
                .name(Component.translatable("treeify.gui.option.disable_all_mushrooms"))
                .binding(
                        false,
                        editService::getDisableAllMushrooms,
                        editService::setDisableAllMushrooms
                )
                .controller(BooleanControllerBuilder::create)
                .build());

        categoryBuilder.group(killSwitchGroup.build());

        OptionGroup.Builder multiplierGroup = OptionGroup.createBuilder()
                .name(Component.translatable("treeify.gui.group.multipliers"));

        multiplierGroup.option(Option.<Float>createBuilder()
                .name(Component.translatable("treeify.gui.option.global_tree_density"))
                .binding(
                        1.0f,
                        editService::getGlobalTreeDensityMultiplier,
                        editService::setGlobalTreeDensityMultiplier
                )
                .controller(opt -> FloatSliderControllerBuilder.create(opt).range(0.0f, 5.0f).step(0.1f))
                .build());

        multiplierGroup.option(Option.<Float>createBuilder()
                .name(Component.translatable("treeify.gui.option.global_mushroom_density"))
                .binding(
                        1.0f,
                        editService::getGlobalMushroomDensityMultiplier,
                        editService::setGlobalMushroomDensityMultiplier
                )
                .controller(opt -> FloatSliderControllerBuilder.create(opt).range(0.0f, 5.0f).step(0.1f))
                .build());

        categoryBuilder.group(multiplierGroup.build());

        builder.category(categoryBuilder.build());
    }
}
