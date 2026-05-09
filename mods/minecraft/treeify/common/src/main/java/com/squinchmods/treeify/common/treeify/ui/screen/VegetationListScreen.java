package com.squinchmods.treeify.common.treeify.ui.screen;

import com.squinchmods.treeify.common.treeify.ui.model.ConfigUiCategoryView;
import com.squinchmods.treeify.common.treeify.ui.model.ConfigUiEntryView;
import com.squinchmods.treeify.common.treeify.ui.service.ConfigUiCatalogService;
import com.squinchmods.treeify.common.treeify.ui.service.ConfigUiEditService;
import com.squinchmods.treeify.common.treeify.ui.shell.TreeifyConfigScreenContext;
import com.squinchmods.treeify.common.treeify.ui.shell.TreeifyConfigTabComposer;
import dev.isxander.yacl3.api.ConfigCategory;
import dev.isxander.yacl3.api.Option;
import dev.isxander.yacl3.api.OptionDescription;
import dev.isxander.yacl3.api.OptionGroup;
import dev.isxander.yacl3.api.YetAnotherConfigLib;
import net.minecraft.network.chat.Component;

/**
 * Composer for the vegetation list tab.
 */
public class VegetationListScreen implements TreeifyConfigTabComposer {

    private final ConfigUiCatalogService catalogService;
    private final ConfigUiEditService editService;

    public VegetationListScreen(ConfigUiCatalogService catalogService, ConfigUiEditService editService) {
        this.catalogService = catalogService;
        this.editService = editService;
    }

    @Override
    public void compose(YetAnotherConfigLib.Builder builder, TreeifyConfigScreenContext context) {
        ConfigCategory.Builder categoryBuilder = ConfigCategory.createBuilder()
                .name(Component.translatable("treeify.gui.category.vegetation"));

        for (ConfigUiCategoryView categoryView : catalogService.getCatalogSnapshot().categories()) {
            OptionGroup.Builder groupBuilder = OptionGroup.createBuilder()
                    .name(categoryView.title());

            for (ConfigUiEntryView entryView : categoryView.entries()) {
                var option = Option.<Boolean>createBuilder()
                        .name(entryView.title())
                        .description(OptionDescription.of(entryView.description().orElse(Component.empty())))
                        .binding(
                                entryView.defaultEnabled(),
                                () -> editService.isEnabled(entryView.id()),
                                newVal -> editService.setEnabled(entryView.id(), newVal)
                        )
                        .customController(opt -> new com.squinchmods.treeify.common.treeify.ui.control.TreeifyBooleanDetailController(
                                opt,
                                entryView.id().value(),
                                (val) -> Component.literal(val ? "Enabled" : "Disabled").withStyle(val ? net.minecraft.ChatFormatting.GREEN : net.minecraft.ChatFormatting.RED),
                                true,
                                (parentScreen, itemId) -> context.openDetail(new com.squinchmods.treeify.common.treeify.ui.model.ConfigUiDetailRoute(entryView.id())),
                                (itemId) -> Component.literal("Edit Feature Details")
                        ))
                        .build();

                groupBuilder.option(option);
            }

            categoryBuilder.group(groupBuilder.build());
        }

        builder.category(categoryBuilder.build());
    }
}
