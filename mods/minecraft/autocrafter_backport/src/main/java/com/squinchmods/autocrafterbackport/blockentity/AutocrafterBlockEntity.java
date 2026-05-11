package com.squinchmods.autocrafterbackport.blockentity;

import com.squinchmods.autocrafterbackport.AutocrafterBackportMod;
import com.squinchmods.autocrafterbackport.block.AutocrafterBlock;
import com.squinchmods.autocrafterbackport.menu.AutocrafterMenu;
import java.util.List;
import java.util.Optional;
import javax.annotation.Nullable;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.NonNullList;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.game.ClientboundBlockEntityDataPacket;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.MenuProvider;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.entity.player.StackedContents;
import net.minecraft.world.inventory.AbstractContainerMenu;
import net.minecraft.world.inventory.CraftingContainer;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.crafting.CraftingRecipe;
import net.minecraft.world.item.crafting.RecipeType;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.common.capabilities.Capability;
import net.minecraftforge.common.capabilities.ForgeCapabilities;
import net.minecraftforge.common.util.LazyOptional;
import net.minecraftforge.items.IItemHandler;

public class AutocrafterBlockEntity extends BlockEntity implements MenuProvider {
  private static final int SLOT_COUNT = 9;
  private final NonNullList<ItemStack> items = NonNullList.withSize(9, ItemStack.EMPTY);
  private final boolean[] enabled = new boolean[9];
  private int nextInsertSlot = 0;
  private final IItemHandler itemHandler = new AutocrafterBlockEntity.AutocrafterItemHandler();
  private LazyOptional<IItemHandler> itemHandlerOptional = LazyOptional.of(() -> this.itemHandler);

  public AutocrafterBlockEntity(BlockPos pos, BlockState state) {
    super(AutocrafterBackportMod.AUTOCRAFTER_BLOCK_ENTITY.get(), pos, state);

    for (int i = 0; i < this.enabled.length; i++) {
      this.enabled[i] = true;
    }
  }

  private void setChangedAndSync() {
    this.setChanged();
    if (this.level != null && !this.level.isClientSide) {
      BlockState state = this.getBlockState();
      this.level.sendBlockUpdated(this.worldPosition, state, state, 3);
    }
  }

  @Override
  public Component getDisplayName() {
    return Component.translatable("container.autocrafter_backport.autocrafter");
  }

  @Override
  @Nullable public AbstractContainerMenu createMenu(
      int containerId, Inventory playerInventory, Player player) {
    return new AutocrafterMenu(containerId, playerInventory, this);
  }

  public NonNullList<ItemStack> getItems() {
    return this.items;
  }

  public boolean isSlotEnabled(int slot) {
    return this.enabled[slot];
  }

  public void toggleSlotEnabled(int slot) {
    if (slot >= 0 && slot < this.enabled.length) {
      this.enabled[slot] = !this.enabled[slot];
      this.setChangedAndSync();
    }
  }

  public void setSlotEnabled(int slot, boolean value) {
    if (slot >= 0 && slot < this.enabled.length) {
      this.enabled[slot] = value;
      this.setChanged();
      if (this.level != null && !this.level.isClientSide) {
        this.level.sendBlockUpdated(
            this.worldPosition, this.getBlockState(), this.getBlockState(), 3);
      }
    }
  }

  @Override
  public CompoundTag getUpdateTag() {
    CompoundTag tag = super.getUpdateTag();
    this.saveAdditional(tag);
    return tag;
  }

  @Override
  public ClientboundBlockEntityDataPacket getUpdatePacket() {
    return ClientboundBlockEntityDataPacket.create(this);
  }

  @Override
  public <T> LazyOptional<T> getCapability(Capability<T> cap, @Nullable Direction side) {
    return cap == ForgeCapabilities.ITEM_HANDLER
        ? this.itemHandlerOptional.cast()
        : super.getCapability(cap, side);
  }

  @Override
  public void invalidateCaps() {
    super.invalidateCaps();
    this.itemHandlerOptional.invalidate();
  }

  @Override
  public void reviveCaps() {
    super.reviveCaps();
    this.itemHandlerOptional = LazyOptional.of(() -> this.itemHandler);
  }

  public ItemStack getCraftingResult() {
    if (this.level == null) {
      return ItemStack.EMPTY;
    } else {
      CraftingContainer craftingContainer = this.buildCraftingContainer();
      Optional<CraftingRecipe> optional =
          this.level
              .getRecipeManager()
              .getRecipeFor(RecipeType.CRAFTING, craftingContainer, this.level);
      if (optional.isEmpty()) {
        return ItemStack.EMPTY;
      } else {
        CraftingRecipe recipe = optional.get();
        return recipe.assemble(craftingContainer, this.level.registryAccess());
      }
    }
  }

  public void tryCraftAndEject() {
    if (this.level != null && !this.level.isClientSide) {
      if (this.level instanceof ServerLevel serverLevel) {
        CraftingContainer var12 = this.buildCraftingContainer();
        Optional<CraftingRecipe> optional =
            serverLevel.getRecipeManager().getRecipeFor(RecipeType.CRAFTING, var12, serverLevel);
        if (optional.isEmpty()) {
          serverLevel.playSound(
              null, this.worldPosition, SoundEvents.DISPENSER_FAIL, SoundSource.BLOCKS, 0.8F, 1.0F);
        } else {
          CraftingRecipe recipe = optional.get();
          ItemStack result = recipe.assemble(var12, serverLevel.registryAccess());
          if (result.isEmpty()) {
            serverLevel.playSound(
                null,
                this.worldPosition,
                SoundEvents.DISPENSER_FAIL,
                SoundSource.BLOCKS,
                0.8F,
                1.0F);
          } else {
            NonNullList<ItemStack> remaining = recipe.getRemainingItems(var12);

            for (int i = 0; i < 9; i++) {
              if (this.enabled[i]) {
                ItemStack in = (ItemStack) this.items.get(i);
                if (!in.isEmpty()) {
                  in.shrink(1);
                  if (in.isEmpty()) {
                    this.items.set(i, ItemStack.EMPTY);
                  }
                }

                ItemStack rem = (ItemStack) remaining.get(i);
                if (!rem.isEmpty()) {
                  ItemStack current = (ItemStack) this.items.get(i);
                  if (current.isEmpty()) {
                    this.items.set(i, rem);
                  } else {
                    ItemStack leftover = this.insertToFront(rem);
                    if (!leftover.isEmpty()) {
                      this.dropToFront(leftover);
                    }
                  }
                }
              }
            }

            ItemStack leftover = this.insertToFront(result.copy());
            if (!leftover.isEmpty()) {
              this.dropToFront(leftover);
            }

            serverLevel.playSound(
                null,
                this.worldPosition,
                SoundEvents.DISPENSER_DISPENSE,
                SoundSource.BLOCKS,
                0.8F,
                1.0F);
            BlockState state = this.getBlockState();
            if (state.getBlock() instanceof AutocrafterBlock) {
              serverLevel.setBlock(
                  this.worldPosition, state.setValue(AutocrafterBlock.CRAFTING, true), 3);
              serverLevel.scheduleTick(this.worldPosition, state.getBlock(), 6);
            }

            this.setChanged();
          }
        }
      }
    }
  }

  private CraftingContainer buildCraftingContainer() {
    NonNullList<ItemStack> grid = NonNullList.withSize(9, ItemStack.EMPTY);

    for (int i = 0; i < 9; i++) {
      grid.set(i, this.enabled[i] ? this.items.get(i).copy() : ItemStack.EMPTY);
    }

    return new AutocrafterBlockEntity.AutocrafterCraftingContainer(grid);
  }

  private ItemStack insertToFront(ItemStack stack) {
    if (this.level == null) {
      return stack;
    } else {
      Direction facing = (Direction) this.getBlockState().getValue(AutocrafterBlock.FACING);
      BlockPos outPos = this.worldPosition.relative(facing);
      BlockEntity be = this.level.getBlockEntity(outPos);
      if (be == null) {
        return stack;
      } else {
        LazyOptional<IItemHandler> cap =
            be.getCapability(ForgeCapabilities.ITEM_HANDLER, facing.getOpposite());
        if (!cap.isPresent()) {
          return stack;
        } else {
          IItemHandler handler = (IItemHandler) cap.orElseThrow(IllegalStateException::new);
          ItemStack remaining = stack;

          for (int slot = 0; slot < handler.getSlots(); slot++) {
            remaining = handler.insertItem(slot, remaining, false);
            if (remaining.isEmpty()) {
              break;
            }
          }

          return remaining;
        }
      }
    }
  }

  private void dropToFront(ItemStack stack) {
    if (this.level != null) {
      Direction facing = this.getBlockState().getValue(AutocrafterBlock.FACING);
      Vec3 center =
          Vec3.atCenterOf(this.worldPosition)
              .add(facing.getStepX() * 0.6, facing.getStepY() * 0.6, facing.getStepZ() * 0.6);
      ItemEntity ent = new ItemEntity(this.level, center.x, center.y, center.z, stack);
      ent.setDefaultPickUpDelay();
      this.level.addFreshEntity(ent);
    }
  }

  @Override
  protected void saveAdditional(CompoundTag tag) {
    super.saveAdditional(tag);
    tag.putInt("NextInsertSlot", this.nextInsertSlot);

    for (int i = 0; i < 9; i++) {
      CompoundTag itemTag = new CompoundTag();
      this.items.get(i).save(itemTag);
      tag.put("Item" + i, itemTag);
      tag.putBoolean("Enabled" + i, this.enabled[i]);
    }
  }

  @Override
  public void load(CompoundTag tag) {
    super.load(tag);
    this.nextInsertSlot = tag.contains("NextInsertSlot") ? tag.getInt("NextInsertSlot") : 0;

    for (int i = 0; i < 9; i++) {
      CompoundTag itemTag = tag.getCompound("Item" + i);
      this.items.set(i, ItemStack.of(itemTag));
      String key = "Enabled" + i;
      this.enabled[i] = tag.contains(key) ? tag.getBoolean(key) : true;
    }
  }

  private static class AutocrafterCraftingContainer implements CraftingContainer {
    private final NonNullList<ItemStack> items;

    private AutocrafterCraftingContainer(NonNullList<ItemStack> items) {
      this.items = items;
    }

    @Override
    public int getWidth() {
      return 3;
    }

    @Override
    public int getHeight() {
      return 3;
    }

    @Override
    public List<ItemStack> getItems() {
      return this.items;
    }

    @Override
    public void fillStackedContents(StackedContents stackedContents) {
      for (int i = 0; i < this.items.size(); i++) {
        stackedContents.accountStack(this.items.get(i));
      }
    }

    @Override
    public int getContainerSize() {
      return this.items.size();
    }

    @Override
    public boolean isEmpty() {
      for (int i = 0; i < this.items.size(); i++) {
        if (!this.items.get(i).isEmpty()) {
          return false;
        }
      }

      return true;
    }

    @Override
    public ItemStack getItem(int slot) {
      return this.items.get(slot);
    }

    @Override
    public ItemStack removeItem(int slot, int amount) {
      ItemStack stack = this.items.get(slot);
      return stack.isEmpty() ? ItemStack.EMPTY : stack.split(amount);
    }

    @Override
    public ItemStack removeItemNoUpdate(int slot) {
      ItemStack stack = this.items.get(slot);
      this.items.set(slot, ItemStack.EMPTY);
      return stack;
    }

    @Override
    public void setItem(int slot, ItemStack stack) {
      this.items.set(slot, stack);
    }

    @Override
    public void setChanged() {}

    @Override
    public boolean stillValid(Player player) {
      return true;
    }

    @Override
    public void clearContent() {
      for (int i = 0; i < this.items.size(); i++) {
        this.items.set(i, ItemStack.EMPTY);
      }
    }
  }

  private class AutocrafterItemHandler implements IItemHandler {
    @Override
    public int getSlots() {
      return SLOT_COUNT;
    }

    @Override
    public ItemStack getStackInSlot(int slot) {
      return slot >= 0 && slot < SLOT_COUNT
          ? AutocrafterBlockEntity.this.items.get(slot)
          : ItemStack.EMPTY;
    }

    @Override
    public ItemStack insertItem(int slot, ItemStack stack, boolean simulate) {
      if (stack.isEmpty()) {
        return ItemStack.EMPTY;
      } else {
        int target = this.findNextInsertSlot(stack);
        if (target < 0) {
          return stack;
        } else {
          ItemStack existing = AutocrafterBlockEntity.this.items.get(target);
          if (!simulate) {
            if (existing.isEmpty()) {
              ItemStack placed = stack.copy();
              placed.setCount(1);
              AutocrafterBlockEntity.this.items.set(target, placed);
            } else {
              existing.grow(1);
            }

            AutocrafterBlockEntity.this.nextInsertSlot = (target + 1) % 9;
            AutocrafterBlockEntity.this.setChangedAndSync();
          }

          ItemStack remaining = stack.copy();
          remaining.shrink(1);
          return remaining.isEmpty() ? ItemStack.EMPTY : remaining;
        }
      }
    }

    private int findNextInsertSlot(ItemStack stack) {
      for (int step = 0; step < SLOT_COUNT; step++) {
        int idx = (AutocrafterBlockEntity.this.nextInsertSlot + step) % SLOT_COUNT;
        if (AutocrafterBlockEntity.this.enabled[idx]
            && AutocrafterBlockEntity.this.items.get(idx).isEmpty()) {
          return idx;
        }
      }

      for (int stepx = 0; stepx < SLOT_COUNT; stepx++) {
        int idx = (AutocrafterBlockEntity.this.nextInsertSlot + stepx) % SLOT_COUNT;
        if (AutocrafterBlockEntity.this.enabled[idx]) {
          ItemStack existing = AutocrafterBlockEntity.this.items.get(idx);
          if (!existing.isEmpty() && ItemStack.isSameItemSameTags(existing, stack)) {
            int max = Math.min(stack.getMaxStackSize(), this.getSlotLimit(idx));
            if (existing.getCount() < max) {
              return idx;
            }
          }
        }
      }

      return -1;
    }

    @Override
    public ItemStack extractItem(int slot, int amount, boolean simulate) {
      return ItemStack.EMPTY;
    }

    @Override
    public int getSlotLimit(int slot) {
      return 64;
    }

    @Override
    public boolean isItemValid(int slot, ItemStack stack) {
      return slot >= 0 && slot < SLOT_COUNT && AutocrafterBlockEntity.this.enabled[slot];
    }
  }
}
