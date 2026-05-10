package com.squinchmods.vegetate.common.vegetate.ui.shell;

import com.squinchmods.vegetate.common.vegetate.ui.model.ConfigUiCatalogSnapshot;
import com.squinchmods.vegetate.common.vegetate.ui.model.ConfigUiCategoryView;
import com.squinchmods.vegetate.common.vegetate.ui.model.ConfigUiEntryView;
import dev.isxander.yacl3.api.ConfigCategory;
import dev.isxander.yacl3.api.Option;
import dev.isxander.yacl3.api.OptionDescription;
import dev.isxander.yacl3.api.OptionGroup;
import dev.isxander.yacl3.api.YetAnotherConfigLib;
import dev.isxander.yacl3.api.controller.BooleanControllerBuilder;
import dev.isxander.yacl3.gui.YACLScreen;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import net.minecraft.ChatFormatting;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;

public final class VegetateConfigScreen {
  private final VegetateConfigScreenContext context;

  public VegetateConfigScreen(VegetateConfigScreenContext context) {
    this.context = Objects.requireNonNull(context, "context cannot be null");
  }

  public Screen generateScreen(Screen parent) {
    var catalogSnapshot = context.catalogService().getCatalogSnapshot();
    var yaclBuilder =
        YetAnotherConfigLib.createBuilder()
            .title(catalogSnapshot.title())
            .save(() -> context.saveService().savePendingChanges());

    composeMushroomPage(yaclBuilder, catalogSnapshot);

    var yaclScreen = (YACLScreen) yaclBuilder.build().generateScreen(parent);
    context.session().loadInto(yaclScreen);

    return yaclScreen;
  }

  public void saveScreenState(YACLScreen screen) {
    context.session().saveFrom(screen);
  }

  private void composeMushroomPage(
      YetAnotherConfigLib.Builder yaclBuilder, ConfigUiCatalogSnapshot snapshot) {
    var categoryBuilder =
        ConfigCategory.createBuilder()
            .name(Component.translatable("vegetate.gui.category.mushrooms"));

    List<Option<Boolean>> allMushroomOptions = new ArrayList<>();

    for (ConfigUiCategoryView categoryView : snapshot.categories()) {
      var groupBuilder = OptionGroup.createBuilder().name(categoryView.title());

      for (ConfigUiEntryView entryView : categoryView.entries()) {
        var option =
            Option.<Boolean>createBuilder()
                .name(entryView.title())
                .description(
                    OptionDescription.createBuilder()
                        .text(entryView.description().orElse(Component.empty()))
                        .build())
                .binding(
                    entryView.defaultEnabled(),
                    () -> context.editService().isEnabled(entryView.id()),
                    newVal -> context.editService().setEnabled(entryView.id(), newVal))
                .controller(
                    opt ->
                        BooleanControllerBuilder.create(opt)
                            .formatValue(
                                val ->
                                    val
                                        ? Component.translatable("vegetate.gui.label.enabled")
                                            .withStyle(ChatFormatting.GREEN)
                                        : Component.translatable("vegetate.gui.label.disabled")
                                            .withStyle(ChatFormatting.RED))
                            .coloured(true))
                .build();

        allMushroomOptions.add(option);
        groupBuilder.option(option);
      }

      categoryBuilder.group(groupBuilder.build());
    }

    var globalGroup =
        OptionGroup.createBuilder().name(Component.translatable("vegetate.gui.group.global"));

    var globalToggle =
        Option.<Boolean>createBuilder()
            .name(Component.translatable("vegetate.gui.option.mushroom_worldgen_global"))
            .description(
                OptionDescription.createBuilder()
                    .text(
                        Component.translatable(
                            "vegetate.gui.option.mushroom_worldgen_global.description"))
                    .build())
            .binding(
                true,
                () -> !context.editService().getDisableAllMushrooms(),
                allowWorldgen -> context.editService().setDisableAllMushrooms(!allowWorldgen))
            .controller(
                opt ->
                    BooleanControllerBuilder.create(opt)
                        .formatValue(
                            val ->
                                val
                                    ? Component.translatable("vegetate.gui.label.enabled")
                                        .withStyle(ChatFormatting.GREEN)
                                    : Component.translatable("vegetate.gui.label.disabled")
                                        .withStyle(ChatFormatting.RED))
                        .coloured(true))
            .addListener(
                (opt, event) -> {
                  for (var mushroomOpt : allMushroomOptions) {
                    mushroomOpt.requestSet(opt.pendingValue());
                  }
                })
            .build();

    globalGroup.option(globalToggle);

    categoryBuilder.group(globalGroup.build());

    yaclBuilder.category(categoryBuilder.build());
  }
}
