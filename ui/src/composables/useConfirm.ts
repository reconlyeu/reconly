/**
 * Composable for confirmation dialogs
 * Uses native browser confirm() for simplicity
 */

export function useConfirm() {
  const confirm = (message: string, title?: string): boolean => {
    const fullMessage = title ? `${title}\n\n${message}` : message;
    return window.confirm(fullMessage);
  };

  return {
    confirm,
    confirmDelete: (itemName: string, itemType: string = 'item'): boolean => {
      return confirm(
        `Are you sure you want to delete "${itemName}"? This action cannot be undone.`,
        `Delete ${itemType}`
      );
    },
  };
}
