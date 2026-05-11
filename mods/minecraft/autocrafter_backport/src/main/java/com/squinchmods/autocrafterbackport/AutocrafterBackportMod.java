package com.squinchmods.autocrafterbackport;

import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.logging.LogUtils;
import com.squinchmods.autocrafterbackport.block.AutocrafterBlock;
import com.squinchmods.autocrafterbackport.blockentity.AutocrafterBlockEntity;
import com.squinchmods.autocrafterbackport.client.AutocrafterScreen;
import com.squinchmods.autocrafterbackport.menu.AutocrafterMenu;
import java.util.Objects;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.MenuScreens;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.arguments.EntityArgument;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.inventory.MenuType;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.CreativeModeTabs;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.entity.BlockEntityType;
import net.minecraft.world.level.block.state.BlockBehaviour.Properties;
import net.minecraft.world.level.material.MapColor;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.common.extensions.IForgeMenuType;
import net.minecraftforge.event.BuildCreativeModeTabContentsEvent;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.event.server.ServerStartingEvent;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.common.Mod.EventBusSubscriber;
import net.minecraftforge.fml.common.Mod.EventBusSubscriber.Bus;
import net.minecraftforge.fml.event.lifecycle.FMLClientSetupEvent;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;
import org.slf4j.Logger;

@Mod("autocrafter_backport")
public class AutocrafterBackportMod {
  public static final String MODID = "autocrafter_backport";
  private static final Logger LOGGER = LogUtils.getLogger();
  public static final DeferredRegister<Block> BLOCKS =
      DeferredRegister.create(ForgeRegistries.BLOCKS, "autocrafter_backport");
  public static final DeferredRegister<Item> ITEMS =
      DeferredRegister.create(ForgeRegistries.ITEMS, "autocrafter_backport");
  public static final DeferredRegister<BlockEntityType<?>> BLOCK_ENTITY_TYPES =
      DeferredRegister.create(ForgeRegistries.BLOCK_ENTITY_TYPES, "autocrafter_backport");
  public static final DeferredRegister<MenuType<?>> MENUS =
      DeferredRegister.create(ForgeRegistries.MENU_TYPES, "autocrafter_backport");
  public static final RegistryObject<Block> AUTOCRAFTER_BLOCK =
      BLOCKS.register(
          "autocrafter",
          () -> new AutocrafterBlock(Properties.of().mapColor(MapColor.METAL).strength(3.5F)));
  public static final RegistryObject<Item> AUTOCRAFTER_BLOCK_ITEM =
      ITEMS.register(
          "autocrafter",
          () ->
              new BlockItem(
                  AUTOCRAFTER_BLOCK.get(), new net.minecraft.world.item.Item.Properties()));
  public static final RegistryObject<BlockEntityType<AutocrafterBlockEntity>>
      AUTOCRAFTER_BLOCK_ENTITY =
          BLOCK_ENTITY_TYPES.register(
              "autocrafter",
              () ->
                  BlockEntityType.Builder.of(AutocrafterBlockEntity::new, AUTOCRAFTER_BLOCK.get())
                      .build(null));
  public static final RegistryObject<MenuType<AutocrafterMenu>> AUTOCRAFTER_MENU =
      MENUS.register("autocrafter", () -> IForgeMenuType.create(AutocrafterMenu::new));

  public AutocrafterBackportMod(FMLJavaModLoadingContext context) {
    IEventBus modEventBus = context.getModEventBus();
    BLOCKS.register(modEventBus);
    ITEMS.register(modEventBus);
    BLOCK_ENTITY_TYPES.register(modEventBus);
    MENUS.register(modEventBus);
    MinecraftForge.EVENT_BUS.register(this);
    modEventBus.addListener(this::addCreative);
  }

  private void addCreative(BuildCreativeModeTabContentsEvent event) {
    if (Objects.equals(event.getTabKey(), CreativeModeTabs.REDSTONE_BLOCKS)) {
      event.accept(AUTOCRAFTER_BLOCK_ITEM);
    }
  }

  @SubscribeEvent
  public void onServerStarting(ServerStartingEvent event) {
    LOGGER.info("HELLO from server starting");
  }

  @SubscribeEvent
  public void onRegisterCommands(RegisterCommandsEvent event) {
    LiteralArgumentBuilder<CommandSourceStack> giveCommand =
        Commands.literal("give")
            .executes(
                ctx -> {
                  ServerPlayer player = ctx.getSource().getPlayerOrException();
                  ItemStack stack = new ItemStack(AUTOCRAFTER_BLOCK_ITEM.get(), 1);
                  boolean ok = player.getInventory().add(stack);
                  if (!ok) {
                    player.drop(stack, false);
                  }

                  return 1;
                })
            .then(
                Commands.argument("player", EntityArgument.player())
                    .executes(
                        ctx -> {
                          ServerPlayer player = EntityArgument.getPlayer(ctx, "player");
                          ItemStack stack = new ItemStack(AUTOCRAFTER_BLOCK_ITEM.get(), 1);
                          boolean ok = player.getInventory().add(stack);
                          if (!ok) {
                            player.drop(stack, false);
                          }

                          return 1;
                        })
                    .then(
                        Commands.argument("count", IntegerArgumentType.integer(1, 64))
                            .executes(
                                ctx -> {
                                  ServerPlayer player = EntityArgument.getPlayer(ctx, "player");
                                  int count = IntegerArgumentType.getInteger(ctx, "count");
                                  ItemStack stack =
                                      new ItemStack(AUTOCRAFTER_BLOCK_ITEM.get(), count);
                                  boolean ok = player.getInventory().add(stack);
                                  if (!ok) {
                                    player.drop(stack, false);
                                  }

                                  return 1;
                                })));

    event
        .getDispatcher()
        .register(
            Commands.literal("autocrafter")
                .requires(source -> source.hasPermission(2))
                .then(giveCommand));
  }

  @EventBusSubscriber(modid = "autocrafter_backport", bus = Bus.MOD, value = Dist.CLIENT)
  public static class ClientModEvents {
    @SubscribeEvent
    public static void onClientSetup(FMLClientSetupEvent event) {
      AutocrafterBackportMod.LOGGER.info("HELLO FROM CLIENT SETUP");
      AutocrafterBackportMod.LOGGER.info(
          "MINECRAFT NAME >> {}", Minecraft.getInstance().getUser().getName());
      var unused =
          event.enqueueWork(
              () ->
                  MenuScreens.register(
                      AutocrafterBackportMod.AUTOCRAFTER_MENU.get(), AutocrafterScreen::new));
    }
  }
}
