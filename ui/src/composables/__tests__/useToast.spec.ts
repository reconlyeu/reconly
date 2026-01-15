import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// We need to test the actual implementation, not the mocked version
// So we'll use vi.doUnmock to get the real module
describe('useToast', () => {
  let originalWindow: typeof window;

  beforeEach(() => {
    vi.resetModules();
    originalWindow = global.window;
  });

  afterEach(() => {
    global.window = originalWindow;
  });

  describe('SSR fallback (no window)', () => {
    it('returns console fallback when window is undefined', async () => {
      // Mock window as undefined for SSR
      vi.stubGlobal('window', undefined);

      // Clear the module cache and re-import
      vi.resetModules();

      // Import the actual module (not mocked)
      const { useToast } = await vi.importActual<typeof import('../useToast')>('../useToast');

      const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      const consoleInfoSpy = vi.spyOn(console, 'info').mockImplementation(() => {});

      const toast = useToast();

      toast.success('Success message');
      toast.error('Error message');
      toast.warning('Warning message');
      toast.info('Info message');

      expect(consoleSpy).toHaveBeenCalledWith('[Toast Success]', 'Success message');
      expect(consoleErrorSpy).toHaveBeenCalledWith('[Toast Error]', 'Error message');
      expect(consoleWarnSpy).toHaveBeenCalledWith('[Toast Warning]', 'Warning message');
      expect(consoleInfoSpy).toHaveBeenCalledWith('[Toast Info]', 'Info message');

      consoleSpy.mockRestore();
      consoleErrorSpy.mockRestore();
      consoleWarnSpy.mockRestore();
      consoleInfoSpy.mockRestore();
      vi.unstubAllGlobals();
    });
  });

  describe('browser environment', () => {
    it('returns toast interface with success, error, warning, info methods', async () => {
      // Import the actual module
      const { useToast } = await vi.importActual<typeof import('../useToast')>('../useToast');

      const toast = useToast();

      expect(typeof toast.success).toBe('function');
      expect(typeof toast.error).toBe('function');
      expect(typeof toast.warning).toBe('function');
      expect(typeof toast.info).toBe('function');
    });

    it('methods are callable without error', async () => {
      // Import the actual module
      const { useToast } = await vi.importActual<typeof import('../useToast')>('../useToast');

      const toast = useToast();

      // These should not throw
      expect(() => toast.success('Test')).not.toThrow();
      expect(() => toast.error('Test')).not.toThrow();
      expect(() => toast.warning('Test')).not.toThrow();
      expect(() => toast.info('Test')).not.toThrow();
    });
  });

  describe('mocked useToast (for other tests)', () => {
    it('mocked version returns expected interface', async () => {
      // Use the mocked version from vitest.setup.ts
      const { useToast } = await import('../useToast');

      const toast = useToast();

      expect(typeof toast.success).toBe('function');
      expect(typeof toast.error).toBe('function');
      expect(typeof toast.warning).toBe('function');
      expect(typeof toast.info).toBe('function');
    });
  });
});
