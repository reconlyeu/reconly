import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useViewMode } from '../useViewMode';

// Import the localStorage mock from setup
import { localStorageMock } from '../../../vitest.setup';

describe('useViewMode', () => {
  beforeEach(() => {
    // Clear localStorage mock before each test
    localStorageMock.clear();
    vi.clearAllMocks();
  });

  describe('initialization', () => {
    it('initializes with default mode (card) when no stored value', () => {
      const { viewMode } = useViewMode('testPage');

      expect(viewMode.value).toBe('card');
    });

    it('initializes with custom default mode when provided', () => {
      const { viewMode } = useViewMode('testPage', 'table');

      expect(viewMode.value).toBe('table');
    });

    it('uses stored value when available', () => {
      localStorageMock.setItem('reconly:viewMode:testPage', 'table');

      const { viewMode } = useViewMode('testPage');

      expect(viewMode.value).toBe('table');
    });

    it('ignores invalid stored value and uses default', () => {
      localStorageMock.setItem('reconly:viewMode:testPage', 'invalid');

      const { viewMode } = useViewMode('testPage');

      expect(viewMode.value).toBe('card');
    });
  });

  describe('setViewMode', () => {
    it('updates viewMode value', () => {
      const { viewMode, setViewMode } = useViewMode('testPage');

      setViewMode('table');

      expect(viewMode.value).toBe('table');
    });

    it('persists to localStorage', async () => {
      const { setViewMode } = useViewMode('testPage');

      setViewMode('table');

      // Wait for the watcher to trigger
      await new Promise((resolve) => setTimeout(resolve, 0));

      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'reconly:viewMode:testPage',
        'table'
      );
    });
  });

  describe('toggleViewMode', () => {
    it('toggles from card to table', () => {
      const { viewMode, toggleViewMode } = useViewMode('testPage', 'card');

      toggleViewMode();

      expect(viewMode.value).toBe('table');
    });

    it('toggles from table to card', () => {
      const { viewMode, toggleViewMode } = useViewMode('testPage', 'table');

      toggleViewMode();

      expect(viewMode.value).toBe('card');
    });
  });

  describe('computed properties', () => {
    it('isCardView is true when viewMode is card', () => {
      const { isCardView, isTableView } = useViewMode('testPage', 'card');

      expect(isCardView.value).toBe(true);
      expect(isTableView.value).toBe(false);
    });

    it('isTableView is true when viewMode is table', () => {
      const { isCardView, isTableView, setViewMode } = useViewMode('testPage', 'card');

      setViewMode('table');

      expect(isCardView.value).toBe(false);
      expect(isTableView.value).toBe(true);
    });
  });

  describe('page isolation', () => {
    it('maintains separate state for different page keys', () => {
      const page1 = useViewMode('page1', 'card');
      const page2 = useViewMode('page2', 'table');

      expect(page1.viewMode.value).toBe('card');
      expect(page2.viewMode.value).toBe('table');
    });

    it('stores values under different keys', async () => {
      const { setViewMode: setMode1 } = useViewMode('digests');
      setMode1('table');

      // Wait for watcher
      await new Promise((resolve) => setTimeout(resolve, 10));

      // Verify the call was made with the correct key
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'reconly:viewMode:digests',
        'table'
      );
    });
  });

  describe('localStorage read', () => {
    it('reads correct key for page', () => {
      localStorageMock.setItem('reconly:viewMode:myPage', 'table');

      useViewMode('myPage');

      expect(localStorageMock.getItem).toHaveBeenCalledWith('reconly:viewMode:myPage');
    });
  });
});
