<script setup lang="ts">
interface Props {
  videoId: string
}

const props = defineProps<Props>()
const isLoaded = ref(false)

function stateChange(event: any) {
  isLoaded.value = event.data === 1
}
</script>

<template>
  <div class="relative flex items-center justify-center my-5">
    <ScriptYouTubePlayer :video-id="props.videoId" @ready="isLoaded = true" @state-change="stateChange">
      <template #awaitingLoad>
        <div class="absolute left-0 top-0 backdrop-blur-xs size-full" />
        <div class="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2">
          <UAlert v-if="!isLoaded" class="mb-5" size="sm" color="secondary" variant="solid">
            <template #title>
              <span>Click to load this video. By doing so, you consent to data being transferred to YouTube.</span>
            </template>
            <template #description>
              <div class="flex items-center justify-center">
                <Icon name="i-simple-icons-youtube" :size="48" />
              </div>
            </template>
          </UAlert>
        </div>
      </template>
    </ScriptYouTubePlayer>
  </div>
</template>
