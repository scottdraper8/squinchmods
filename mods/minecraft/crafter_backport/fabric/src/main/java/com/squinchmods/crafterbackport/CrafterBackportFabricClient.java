package com.squinchmods.crafterbackport;

import com.squinchmods.crafterbackport.client.CrafterScreen;
import net.fabricmc.api.ClientModInitializer;
import net.minecraft.client.gui.screens.MenuScreens;

public class CrafterBackportFabricClient implements ClientModInitializer {
  @Override
  public void onInitializeClient() {
    MenuScreens.register(Platform.CRAFTER_MENU.get(), CrafterScreen::new);
  }
}
