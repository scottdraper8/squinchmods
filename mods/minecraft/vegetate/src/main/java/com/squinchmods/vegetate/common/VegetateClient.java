package com.squinchmods.vegetate.common;

import com.squinchmods.vegetate.common.vegetate.ui.service.VegetateConfigUiCatalogService;
import com.squinchmods.vegetate.common.vegetate.ui.service.VegetateConfigUiEditService;
import com.squinchmods.vegetate.common.vegetate.ui.service.VegetateConfigUiSaveService;
import com.squinchmods.vegetate.common.vegetate.ui.shell.VegetateConfigScreen;
import com.squinchmods.vegetate.common.vegetate.ui.shell.VegetateConfigScreenContext;
import com.squinchmods.vegetate.common.vegetate.ui.state.VegetateConfigSessionImpl;
import com.squinchmods.vegetate.common.vegetate.worldgen.discovery.VegetationWorldgenDataProvider;
import net.minecraft.client.gui.screens.Screen;
import org.jetbrains.annotations.Nullable;

public final class VegetateClient {
  @Nullable private static VegetateConfigScreen configScreen;

  public static void init() {}

  public static Screen getConfigScreen(Screen parent) {
    var index = VegetationWorldgenDataProvider.discover();

    var catalogService = new VegetateConfigUiCatalogService(Vegetate.getConfigService(), index);
    var editService = new VegetateConfigUiEditService(Vegetate.getConfigService(), index);
    var saveService = new VegetateConfigUiSaveService(Vegetate.getConfigService(), editService);
    var session = new VegetateConfigSessionImpl();

    var context =
        new VegetateConfigScreenContext(catalogService, editService, saveService, session);

    configScreen = new VegetateConfigScreen(context);
    return configScreen.generateScreen(parent);
  }

  @Nullable public static VegetateConfigScreen getConfigScreen() {
    return configScreen;
  }
}
