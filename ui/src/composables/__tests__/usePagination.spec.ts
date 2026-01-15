import { describe, it, expect } from 'vitest';
import { ref } from 'vue';
import { usePagination } from '../usePagination';

describe('usePagination', () => {
  describe('initialization', () => {
    it('initializes with default values', () => {
      const { page, perPage, offset, totalPages } = usePagination();

      expect(page.value).toBe(1);
      expect(perPage.value).toBe(10);
      expect(offset.value).toBe(0);
      expect(totalPages.value).toBe(1);
    });

    it('initializes with custom page size', () => {
      const { perPage } = usePagination({ pageSize: 25 });

      expect(perPage.value).toBe(25);
    });

    it('initializes with custom initial page', () => {
      const { page } = usePagination({ initialPage: 3 });

      expect(page.value).toBe(3);
    });

    it('calculates totalPages from total ref', () => {
      const total = ref(100);
      const { totalPages } = usePagination({ total, pageSize: 10 });

      expect(totalPages.value).toBe(10);
    });
  });

  describe('offset calculation', () => {
    it('calculates correct offset for page 1', () => {
      const { offset } = usePagination({ pageSize: 10 });

      expect(offset.value).toBe(0);
    });

    it('calculates correct offset for page 2', () => {
      const { page, offset } = usePagination({ pageSize: 10 });
      page.value = 2;

      expect(offset.value).toBe(10);
    });

    it('calculates correct offset for page 5 with custom page size', () => {
      const { page, offset } = usePagination({ pageSize: 25 });
      page.value = 5;

      expect(offset.value).toBe(100);
    });
  });

  describe('navigation flags', () => {
    it('hasNext is false when on last page', () => {
      const total = ref(30);
      const { page, hasNext } = usePagination({ total, pageSize: 10 });
      page.value = 3;

      expect(hasNext.value).toBe(false);
    });

    it('hasNext is true when not on last page', () => {
      const total = ref(30);
      const { hasNext } = usePagination({ total, pageSize: 10 });

      expect(hasNext.value).toBe(true);
    });

    it('hasPrev is false on first page', () => {
      const { hasPrev } = usePagination();

      expect(hasPrev.value).toBe(false);
    });

    it('hasPrev is true when not on first page', () => {
      const { page, hasPrev } = usePagination();
      page.value = 2;

      expect(hasPrev.value).toBe(true);
    });

    it('isFirstPage is true on page 1', () => {
      const { isFirstPage } = usePagination();

      expect(isFirstPage.value).toBe(true);
    });

    it('isFirstPage is false on page 2', () => {
      const { page, isFirstPage } = usePagination();
      page.value = 2;

      expect(isFirstPage.value).toBe(false);
    });

    it('isLastPage is true on last page', () => {
      const total = ref(25);
      const { page, isLastPage } = usePagination({ total, pageSize: 10 });
      page.value = 3;

      expect(isLastPage.value).toBe(true);
    });

    it('isLastPage is false when not on last page', () => {
      const total = ref(25);
      const { isLastPage } = usePagination({ total, pageSize: 10 });

      expect(isLastPage.value).toBe(false);
    });
  });

  describe('navigation methods', () => {
    it('nextPage increments page', () => {
      const total = ref(100);
      const { page, nextPage } = usePagination({ total, pageSize: 10 });

      nextPage();

      expect(page.value).toBe(2);
    });

    it('nextPage does not go past last page', () => {
      const total = ref(20);
      const { page, nextPage } = usePagination({ total, pageSize: 10 });
      page.value = 2;

      nextPage();

      expect(page.value).toBe(2);
    });

    it('prevPage decrements page', () => {
      const { page, prevPage } = usePagination();
      page.value = 3;

      prevPage();

      expect(page.value).toBe(2);
    });

    it('prevPage does not go below 1', () => {
      const { page, prevPage } = usePagination();

      prevPage();

      expect(page.value).toBe(1);
    });

    it('goToPage sets specific page', () => {
      const total = ref(100);
      const { page, goToPage } = usePagination({ total, pageSize: 10 });

      goToPage(5);

      expect(page.value).toBe(5);
    });

    it('goToPage ignores invalid page numbers (too low)', () => {
      const { page, goToPage } = usePagination();
      page.value = 5;

      goToPage(0);

      expect(page.value).toBe(5);
    });

    it('goToPage ignores invalid page numbers (too high)', () => {
      const total = ref(50);
      const { page, goToPage } = usePagination({ total, pageSize: 10 });

      goToPage(10);

      expect(page.value).toBe(1);
    });
  });

  describe('reset', () => {
    it('resets page to 1', () => {
      const { page, reset } = usePagination();
      page.value = 5;

      reset();

      expect(page.value).toBe(1);
    });
  });

  describe('setPageSize', () => {
    it('updates page size', () => {
      const { perPage, setPageSize } = usePagination();

      setPageSize(50);

      expect(perPage.value).toBe(50);
    });

    it('resets page to 1 when page size changes', () => {
      const { page, setPageSize } = usePagination();
      page.value = 5;

      setPageSize(50);

      expect(page.value).toBe(1);
    });

    it('recalculates totalPages when page size changes', () => {
      const total = ref(100);
      const { totalPages, setPageSize } = usePagination({ total, pageSize: 10 });

      expect(totalPages.value).toBe(10);

      setPageSize(25);

      expect(totalPages.value).toBe(4);
    });
  });

  describe('reactive total', () => {
    it('updates totalPages when total changes', () => {
      const total = ref(50);
      const { totalPages } = usePagination({ total, pageSize: 10 });

      expect(totalPages.value).toBe(5);

      total.value = 100;

      expect(totalPages.value).toBe(10);
    });

    it('handles zero total', () => {
      const total = ref(0);
      const { totalPages } = usePagination({ total, pageSize: 10 });

      expect(totalPages.value).toBe(1);
    });
  });

  describe('edge cases', () => {
    it('handles total not evenly divisible by page size', () => {
      const total = ref(23);
      const { totalPages } = usePagination({ total, pageSize: 10 });

      expect(totalPages.value).toBe(3);
    });

    it('handles single item', () => {
      const total = ref(1);
      const { totalPages, hasNext, hasPrev } = usePagination({ total, pageSize: 10 });

      expect(totalPages.value).toBe(1);
      expect(hasNext.value).toBe(false);
      expect(hasPrev.value).toBe(false);
    });
  });
});
