<script setup lang="ts">
import { human } from '@/api/client'
defineProps<{ value: string }>()
</script>
<template><span class="status" :class="value"><i></i>{{ human(value) }}</span></template>
