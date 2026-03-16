<template>
  <div id="app">
    <h1>{{ title }}</h1>
    <button @click="increment">Count: {{ count }}</button>
  </div>
</template>

<script>
export default {
    data() {
        return {
            title: 'My App',
            count: 0
        };
    },

    methods: {
        increment() {
            this.count++;
        },

        reset() {
            this.count = 0;
        }
    },

    computed: {
        doubleCount() {
            return this.count * 2;
        }
    }
}
</script>

<style>
#app {
    font-family: sans-serif;
    text-align: center;
}
button {
    padding: 8px 16px;
}
</style>
