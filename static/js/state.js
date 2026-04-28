export let currentLoopId = '';
export let projectScores = {};
export let activeWorkers = [];
export let statusEntries = [];
export let projectRepoMap = {};
export let eventsGraphVisible = false;

export function setCurrentLoopId(v) { currentLoopId = v; }
export function setProjectScores(v) { projectScores = v; }
export function setActiveWorkers(v) { activeWorkers = v; }
export function setStatusEntries(v) { statusEntries = v; }
export function setProjectRepoMap(v) { projectRepoMap = v; }
export function setEventsGraphVisible(v) { eventsGraphVisible = v; }
