import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import DynamicConfigForm from '../DynamicConfigForm.vue';
import type { ConfigField } from '@/types/entities';

// Mock the i18n strings
vi.mock('@/i18n/en', () => ({
  strings: {
    dynamicForm: {
      pathPlaceholder: 'Enter path...',
      selectPlaceholder: 'Select an option...',
      secretPlaceholder: 'Enter value...',
      showSecret: 'Show value',
      hideSecret: 'Hide value',
      setViaEnv: 'ENV',
      noFields: 'No configuration fields',
      validation: {
        required: 'This field is required',
        invalidNumber: 'Please enter a valid number',
        minValue: 'Value must be at least {min}',
        maxValue: 'Value must be at most {max}',
      },
    },
  },
}));

describe('DynamicConfigForm', () => {
  // Helper to create field schemas
  const createStringField = (overrides: Partial<ConfigField> = {}): ConfigField => ({
    key: 'test_string',
    type: 'string',
    label: 'Test String',
    description: 'A test string field',
    ...overrides,
  });

  const createIntegerField = (overrides: Partial<ConfigField> = {}): ConfigField => ({
    key: 'test_integer',
    type: 'integer',
    label: 'Test Integer',
    description: 'A test integer field',
    ...overrides,
  });

  const createBooleanField = (overrides: Partial<ConfigField> = {}): ConfigField => ({
    key: 'test_boolean',
    type: 'boolean',
    label: 'Test Boolean',
    description: 'A test boolean field',
    ...overrides,
  });

  const createPathField = (overrides: Partial<ConfigField> = {}): ConfigField => ({
    key: 'test_path',
    type: 'path',
    label: 'Test Path',
    description: 'A test path field',
    ...overrides,
  });

  const createSelectField = (overrides: Partial<ConfigField> = {}): ConfigField => ({
    key: 'test_select',
    type: 'select',
    label: 'Test Select',
    description: 'A test select field',
    options: [
      { value: 'option1', label: 'Option 1' },
      { value: 'option2', label: 'Option 2' },
    ],
    ...overrides,
  });

  const createSecretField = (overrides: Partial<ConfigField> = {}): ConfigField => ({
    key: 'test_secret',
    type: 'secret',
    label: 'Test Secret',
    description: 'A test secret field',
    ...overrides,
  });

  describe('field type rendering', () => {
    it('renders string field as text input', () => {
      const schema = [createStringField()];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      const input = wrapper.find('input[type="text"]');
      expect(input.exists()).toBe(true);
      expect(wrapper.text()).toContain('Test String');
    });

    it('renders integer field as number input', () => {
      const schema = [createIntegerField()];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      const input = wrapper.find('input[type="number"]');
      expect(input.exists()).toBe(true);
      expect(wrapper.text()).toContain('Test Integer');
    });

    it('renders boolean field as toggle switch', () => {
      const schema = [createBooleanField()];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      // ToggleSwitch component should be rendered
      expect(wrapper.findComponent({ name: 'ToggleSwitch' }).exists()).toBe(true);
      expect(wrapper.text()).toContain('A test boolean field');
    });

    it('renders path field with folder icon', () => {
      const schema = [createPathField()];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      // Path field should render with monospace font and icon container
      const pathContainer = wrapper.find('.font-mono');
      expect(pathContainer.exists()).toBe(true);
      expect(wrapper.text()).toContain('Test Path');
    });

    it('renders select field as dropdown', () => {
      const schema = [createSelectField()];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      const select = wrapper.find('select');
      expect(select.exists()).toBe(true);

      const options = select.findAll('option');
      // First option is placeholder, then the 2 actual options
      expect(options.length).toBe(3);
      expect(options[1].text()).toBe('Option 1');
      expect(options[2].text()).toBe('Option 2');
    });

    it('renders secret field as password input', () => {
      const schema = [createSecretField()];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      const input = wrapper.find('input[type="password"]');
      expect(input.exists()).toBe(true);
    });

    it('renders empty state when schema is empty', () => {
      const wrapper = mount(DynamicConfigForm, {
        props: { schema: [], values: {} },
      });

      expect(wrapper.text()).toContain('No configuration fields');
    });

    it('renders field with type=secret as password input', () => {
      // Use type='secret' directly to test the secret field rendering
      const schema: ConfigField[] = [{
        key: 'api_key',
        type: 'secret',
        label: 'API Key',
        description: 'Secret API key',
      }];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      // The secret field renders as password input
      const input = wrapper.find('input[type="password"]');
      expect(input.exists()).toBe(true);
    });
  });

  describe('required field validation', () => {
    it('shows asterisk for required fields', () => {
      const schema = [createStringField({ required: true })];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      expect(wrapper.html()).toContain('*');
    });

    it('does not show asterisk for optional fields', () => {
      const schema = [createStringField({ required: false })];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      // Check that there's no asterisk in the label area
      const label = wrapper.find('label');
      expect(label.html()).not.toContain('*');
    });

    it('shows validation error for empty required field after blur', async () => {
      const schema = [createStringField({ required: true })];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      const input = wrapper.find('input');
      await input.trigger('blur');

      expect(wrapper.text()).toContain('This field is required');
    });

    it('does not show validation error before field is touched', () => {
      const schema = [createStringField({ required: true })];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      expect(wrapper.text()).not.toContain('This field is required');
    });

    it('emits validation-change with false for invalid form', async () => {
      const schema = [createStringField({ required: true })];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      await nextTick();

      const validationEvents = wrapper.emitted('validation-change');
      expect(validationEvents).toBeTruthy();
      // Initial emit should be false (form invalid due to required field)
      expect(validationEvents![0]).toEqual([false]);
    });

    it('emits validation-change with true for valid form', async () => {
      const schema = [createStringField({ required: true })];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: { test_string: 'value' } },
      });

      await nextTick();

      const validationEvents = wrapper.emitted('validation-change');
      expect(validationEvents).toBeTruthy();
      expect(validationEvents![0]).toEqual([true]);
    });

    it('validates integer min/max constraints', async () => {
      const schema = [createIntegerField({ min: 1, max: 10 })];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: { test_integer: 0 } },
      });

      const input = wrapper.find('input[type="number"]');
      await input.trigger('blur');

      expect(wrapper.text()).toContain('Value must be at least 1');
    });
  });

  describe('v-model binding', () => {
    it('emits update:values when string field changes', async () => {
      const schema = [createStringField()];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      const input = wrapper.find('input[type="text"]');
      await input.setValue('new value');

      const updateEvents = wrapper.emitted('update:values');
      expect(updateEvents).toBeTruthy();
      expect(updateEvents![0]).toEqual([{ test_string: 'new value' }]);
    });

    it('emits update:values when integer field changes', async () => {
      const schema = [createIntegerField()];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      const input = wrapper.find('input[type="number"]');
      await input.setValue('42');

      const updateEvents = wrapper.emitted('update:values');
      expect(updateEvents).toBeTruthy();
      expect(updateEvents![0]).toEqual([{ test_integer: 42 }]);
    });

    it('emits update:values when boolean field changes', async () => {
      const schema = [createBooleanField()];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: { test_boolean: false } },
      });

      const toggle = wrapper.findComponent({ name: 'ToggleSwitch' });
      await toggle.vm.$emit('update:modelValue', true);

      const updateEvents = wrapper.emitted('update:values');
      expect(updateEvents).toBeTruthy();
      expect(updateEvents![0]).toEqual([{ test_boolean: true }]);
    });

    it('emits update:values when select field changes', async () => {
      const schema = [createSelectField()];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      const select = wrapper.find('select');
      await select.setValue('option2');

      const updateEvents = wrapper.emitted('update:values');
      expect(updateEvents).toBeTruthy();
      expect(updateEvents![0]).toEqual([{ test_select: 'option2' }]);
    });

    it('displays initial values correctly', () => {
      const schema = [createStringField()];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: { test_string: 'initial value' } },
      });

      const input = wrapper.find('input[type="text"]');
      expect((input.element as HTMLInputElement).value).toBe('initial value');
    });

    it('uses default value when no value provided', () => {
      const schema = [createStringField({ default: 'default value' })];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      const input = wrapper.find('input[type="text"]');
      expect((input.element as HTMLInputElement).value).toBe('default value');
    });

    it('preserves existing values when updating a single field', async () => {
      const schema = [
        createStringField({ key: 'field1' }),
        createStringField({ key: 'field2' }),
      ];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: { field1: 'value1', field2: 'value2' } },
      });

      const inputs = wrapper.findAll('input[type="text"]');
      await inputs[0].setValue('new value1');

      const updateEvents = wrapper.emitted('update:values');
      expect(updateEvents![0]).toEqual([{ field1: 'new value1', field2: 'value2' }]);
    });
  });

  describe('secret field masking', () => {
    it('renders secret field as password input by default', () => {
      const schema = [createSecretField()];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      const input = wrapper.find('input');
      expect(input.attributes('type')).toBe('password');
    });

    it('shows toggle button when secret is masked', () => {
      const schema = [createSecretField()];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      // Toggle button should exist for secret fields
      const button = wrapper.find('button');
      expect(button.exists()).toBe(true);
      expect(button.attributes('aria-label')).toBe('Show value');
    });

    it('toggles to text input when visibility button clicked', async () => {
      const schema = [createSecretField()];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      // Click the visibility toggle button
      const button = wrapper.find('button');
      await button.trigger('click');

      const input = wrapper.find('input');
      expect(input.attributes('type')).toBe('text');
    });

    it('shows hide button when secret is visible', async () => {
      const schema = [createSecretField()];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      const button = wrapper.find('button');
      await button.trigger('click');

      // After clicking, aria-label should change to "Hide value"
      expect(button.attributes('aria-label')).toBe('Hide value');
    });

    it('toggles back to password input on second click', async () => {
      const schema = [createSecretField()];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      const button = wrapper.find('button');
      await button.trigger('click'); // Show
      await button.trigger('click'); // Hide

      const input = wrapper.find('input');
      expect(input.attributes('type')).toBe('password');
    });

    it('does not show toggle button when field is disabled', () => {
      const schema = [createSecretField({ editable: false })];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      const button = wrapper.find('button');
      expect(button.exists()).toBe(false);
    });
  });

  describe('disabled state', () => {
    it('disables all inputs when disabled prop is true', () => {
      const schema = [
        createStringField(),
        createIntegerField(),
        createSelectField(),
      ];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {}, disabled: true },
      });

      const inputs = wrapper.findAll('input');
      const selects = wrapper.findAll('select');

      inputs.forEach((input) => {
        expect(input.attributes('disabled')).toBeDefined();
      });
      selects.forEach((select) => {
        expect(select.attributes('disabled')).toBeDefined();
      });
    });

    it('disables field when editable is false', () => {
      const schema = [createStringField({ editable: false })];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      const input = wrapper.find('input');
      expect(input.attributes('disabled')).toBeDefined();
    });

    it('shows ENV badge when field has env_var and is not editable', () => {
      const schema = [createStringField({ env_var: 'MY_ENV_VAR', editable: false })];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      expect(wrapper.text()).toContain('ENV');
    });
  });

  describe('select field with dynamic options', () => {
    it('uses options_from to get options from optionsData', () => {
      const schema = [createSelectField({
        options: undefined,
        options_from: 'models'
      })];
      const optionsData = {
        models: [
          { value: 'gpt-4', label: 'GPT-4' },
          { value: 'gpt-3.5', label: 'GPT-3.5' },
        ],
      };
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {}, optionsData },
      });

      const select = wrapper.find('select');
      const options = select.findAll('option');

      // Placeholder + 2 actual options
      expect(options.length).toBe(3);
      expect(options[1].text()).toBe('GPT-4');
      expect(options[2].text()).toBe('GPT-3.5');
    });
  });

  describe('exposed methods', () => {
    it('exposes isValid computed property', async () => {
      const schema = [createStringField({ required: true })];
      const wrapper = mount(DynamicConfigForm, {
        props: { schema, values: {} },
      });

      expect(wrapper.vm.isValid).toBe(false);

      await wrapper.setProps({ values: { test_string: 'value' } });
      expect(wrapper.vm.isValid).toBe(true);
    });
  });
});
