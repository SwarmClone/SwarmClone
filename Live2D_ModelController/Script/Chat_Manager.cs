using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;

public class Chat_Manager : MonoBehaviour
{
    public TMP_Text chat_text;
    public TMP_InputField chat_input;
    public float text_wait_time=0.1f;

    public Model_Manager model_Manager;

    

    public void UpdateInputField_Enter()
    {
        SetSomeText(chat_input.text);
        print("Œƒ±æ ‰»Î");
    }
    public void SetSomeText(string text)
    {
        StartCoroutine(Model_talking(text));
    }
    IEnumerator Model_talking(string text)
    {
        foreach (var item in text)
        {
            chat_text.text += item;
            print(item);

            model_Manager.isTalking = true;          

            yield return new WaitForSeconds(text_wait_time);
        }
        model_Manager.isTalking = false;
        StopAllCoroutines();
    }


}
