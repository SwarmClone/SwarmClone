using Live2D.Cubism.Core;
using System.Collections;
using UnityEngine;
using UnityEngine.UI;
public class Model_Manager : MonoBehaviour
{
    // 引用Live2D模型组件
    private CubismModel model;
    public Slider slider;
    public float testValue;

    //观看方向
    [Header("观看方向")]
    public Vector2 look_pos;  
    private Vector2 curr_pos,target_pos;
    bool isLooking;

    //头的角度
    public float head_angle;
    //眨眼
    [Header("眨眼")]
    public float blink_OpenValue;
    float blink_timer;
    public float blink_Speed;
    bool isOpen_Eyes, isClose_Eyes;

    //呼吸
    [Header("呼吸")]
    public float breathe_value;
    
    //说话
    [Header("说话")]
    public float talk_value;
    float talk_timer;
    public float talk_Speed;
    bool isOpen_Talk, isClose_Talk;
    public bool isTalking;




    private void Start()
    {
        model = GameObject.FindGameObjectWithTag("Live2D_Model").GetComponent<CubismModel>();

        StartCoroutine(breathe());
        StartCoroutine(Random_Pos());
        blink_OpenValue = Random.Range(0.6f,1.2f);
        blink_timer = Random.Range(1.0f,8.0f);

    }



    IEnumerator breathe()
    {
        float interval = 1.0f / 100.0f;
        while (true)
        {
            breathe_value += interval;
            if (breathe_value >= 1 || breathe_value<=0)
            {
                interval *= -1;

            }
            yield return new WaitForSeconds(0.03f);
        }
    }

    private void Update()
    {
        UpdateValue();
        

        Blink();
        Talk();

    }
    private void UpdateValue()
    {
        //角度X
        model.Parameters[0].Value = look_pos.x;
        //角度Y
        model.Parameters[1].Value = look_pos.y;
        //角度Z
        //model.Parameters[2].Value = head_angle;

        //脸颊泛红
        //model.Parameters[3].Value = ;
        //左眼开闭
        model.Parameters[4].Value = blink_OpenValue;
        //左眼微笑
        //model.Parameters[5].Value = ;
        //右眼开闭
        model.Parameters[6].Value = blink_OpenValue;
        //右眼微笑
        //model.Parameters[7].Value = ;

        //眼珠X
        model.Parameters[8].Value = look_pos.x/30;
        //眼珠Y
        model.Parameters[9].Value = look_pos.y/30;
        //左眉变形
        //model.Parameters[10].Value = ;
        //右眉变形
        //model.Parameters[11].Value = ;
        //嘴变形
        //model.Parameters[12].Value = ;
        //嘴开合
        model.Parameters[13].Value = talk_value;
        //身体旋转X
        model.Parameters[14].Value = look_pos.x/3;
        //身体旋转Y
        model.Parameters[15].Value = look_pos.y/3;
        //身体旋转Z
        //model.Parameters[16].Value = ;
        //身体旋转Z
        //model.Parameters[16].Value = ;
        //呼吸
        model.Parameters[17].Value = breathe_value;
        //左臂 A
        model.Parameters[18].Value = breathe_value * 1.5f;
        //右臂 B
        model.Parameters[19].Value = breathe_value * 1.5f;

        //胸部摇动
        //model.Parameters[20].Value = ;
        //头发摇动 前
        //model.Parameters[21].Value = ;
        //头发摇动 侧
        //model.Parameters[22].Value = ;
        //头发摇动 后
        //model.Parameters[23].Value = ;
        //辫子的摇动
        //model.Parameters[24].Value = ;
        //蝴蝶结的摇动
        //model.Parameters[25].Value = ;
        //短裙的摇动
        //model.Parameters[26].Value = ;
        //发饰的摇动
        //model.Parameters[27].Value = ;
        model.ForceUpdateNow();
    }

    //眨眼方法
    private void Blink()
    {
        if (blink_timer <= 0)
        {
            if (isClose_Eyes && !isOpen_Eyes)
            {
                //睁眼
                blink_OpenValue += Time.deltaTime * blink_Speed;
                if (blink_OpenValue >= 1.2f) { isOpen_Eyes = true; }
            }
            else if (isOpen_Eyes)
            {
                isClose_Eyes = false;
                isOpen_Eyes = false;
                blink_timer = Random.Range(1.0f, 8.0f);
            }
            else
            {
                //闭眼
                blink_OpenValue -= Time.deltaTime * blink_Speed;
                if (blink_OpenValue <= 0) { isClose_Eyes = true; }
            }
        }
        else
        {
            blink_timer -= Time.deltaTime;
        }
    }
    //说话方法
    private void Talk()
    {
        if (isTalking)
        {
            if (isClose_Talk && !isOpen_Talk)
            {
                //开
                talk_value += Time.deltaTime*talk_Speed;
                if (talk_value >= 1f) { isOpen_Talk = true; }
            }
            else if (isOpen_Talk)
            {
                isClose_Talk = false;
                isOpen_Talk = false;
                talk_timer = 1;
            }
            else
            {
                //闭
                talk_value -= Time.deltaTime * talk_Speed;
                if (talk_value <= 0) { isClose_Talk = true; }
            }
        }
        else
        {
            if (talk_value <= 0) { return; }
            talk_value -= Time.deltaTime * talk_Speed;
        }
    }

    IEnumerator Random_Pos()
    {
        float timer=0;
        float lerp_Value = 0f;
        curr_pos = look_pos;
        target_pos = new Vector2(Random.Range(-30, 31), Random.Range(-30, 31));
        while (true)
        {
            if (timer < 3)
            {
                timer += Time.deltaTime;
            }
            else
            {
                lerp_Value += Time.deltaTime * testValue;
                look_pos = Vector2.Lerp(curr_pos, target_pos, lerp_Value);
                if (lerp_Value >= 1)
                {
                    lerp_Value = 0;
                    timer = 0;
                    curr_pos = look_pos;
                    target_pos = new Vector2(Random.Range(-30, 31), Random.Range(-30, 31));
                }
            }

            yield return new WaitForSeconds(0.01f);
        }
    }
    public void BindingValue()
    {
        testValue = slider.value;
    }
}
