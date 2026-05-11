package com.squinchmods.autocrafterbackport.client;

import com.mojang.blaze3d.systems.RenderSystem;
import com.squinchmods.autocrafterbackport.menu.AutocrafterMenu;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.screens.inventory.AbstractContainerScreen;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.entity.player.Inventory;

public class AutocrafterScreen extends AbstractContainerScreen<AutocrafterMenu> {
  private static final ResourceLocation BG =
      ResourceLocation.fromNamespaceAndPath(
          "autocrafter_backport", "textures/gui/container/crafter.png");

  public AutocrafterScreen(AutocrafterMenu menu, Inventory playerInventory, Component title) {
    super(menu, playerInventory, title);
    this.imageWidth = 176;
    this.imageHeight = 166;
  }

  @Override
  protected void init() {
    super.init();
  }

  @Override
  protected void renderBg(GuiGraphics gfx, float partialTick, int mouseX, int mouseY) {
    RenderSystem.setShaderColor(1.0F, 1.0F, 1.0F, 1.0F);
    gfx.blit(BG, this.leftPos, this.topPos, 0, 0, this.imageWidth, this.imageHeight);
    int left = this.leftPos;
    int top = this.topPos;

    for (int row = 0; row < 3; row++) {
      for (int col = 0; col < 3; col++) {
        int slot = col + row * 3;
        if (!((AutocrafterMenu) this.menu).isSlotEnabledClient(slot)) {
          int x = left + 26 + col * 18;
          int y = top + 17 + row * 18;
          gfx.fill(x, y, x + 16, y + 16, -2001686352);
          gfx.fill(x, y, x + 16, y + 1, -1593835521);
          gfx.fill(x, y, x + 1, y + 16, -1593835521);
          gfx.fill(x, y + 15, x + 16, y + 16, -1603901850);
          gfx.fill(x + 15, y, x + 16, y + 16, -1603901850);
        }
      }
    }
  }

  @Override
  public boolean mouseClicked(double mouseX, double mouseY, int button) {
    if (button == 1 && this.minecraft != null && this.minecraft.gameMode != null) {
      int left = this.leftPos;
      int top = this.topPos;
      int startX = left + 26;
      int startY = top + 17;
      if (mouseX >= startX && mouseX < startX + 54 && mouseY >= startY && mouseY < startY + 54) {
        int col = (int) ((mouseX - startX) / 18.0);
        int row = (int) ((mouseY - startY) / 18.0);
        int slot = col + row * 3;
        this.minecraft.gameMode.handleInventoryButtonClick(
            ((AutocrafterMenu) this.menu).containerId, slot);
        return true;
      }
    }

    return super.mouseClicked(mouseX, mouseY, button);
  }

  @Override
  public void render(GuiGraphics gfx, int mouseX, int mouseY, float partialTick) {
    this.renderBackground(gfx);
    super.render(gfx, mouseX, mouseY, partialTick);
    this.renderTooltip(gfx, mouseX, mouseY);
  }

  @Override
  protected void renderLabels(GuiGraphics gfx, int mouseX, int mouseY) {}
}
