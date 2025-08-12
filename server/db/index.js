let tempStorage = [];

export default {
  saveQuestionnaire: async (data) => {
    tempStorage.push(data);
  },
  getAllQuestionnaires: async () => {
    return tempStorage;
  }
};