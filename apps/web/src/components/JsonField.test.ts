import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import JsonField from './JsonField.vue'
it('keeps invalid text visible without overwriting the last valid value', async () => {
  const wrapper = mount(JsonField, { props: { modelValue: { answer: 42 }, label: 'Output' } })
  await wrapper.find('textarea').setValue('{ broken')
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  expect(wrapper.find('textarea').attributes('aria-invalid')).toBe('true')
  await wrapper.setProps({ modelValue: { answer: 42 } })
  expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('{ broken')
  await wrapper.find('textarea').setValue('null')
  expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([null])
  expect(wrapper.find('textarea').attributes('aria-invalid')).toBe('false')
})
it('rejects arrays when an object is required', async () => {
  const wrapper = mount(JsonField, { props: { modelValue: {}, label: 'Slices', objectOnly: true } })
  await wrapper.find('textarea').setValue('[]')
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  expect(wrapper.text()).toContain('Use a JSON object')
})
