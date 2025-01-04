using Live2D.Cubism.Core;
using System.Collections;
using UnityEngine;
using UnityEngine.UI;
public class Model_Manager : MonoBehaviour
{
    // ����Live2Dģ�����
    private CubismModel model;
    public Slider slider;
    public float testValue;

    //�ۿ�����
    [Header("�ۿ�����")]
    public Vector2 look_pos;  
    private Vector2 curr_pos,target_pos;
    bool isLooking;

    //ͷ�ĽǶ�
    public float head_angle;
    //գ��
    [Header("գ��")]
    public float blink_OpenValue;
    float blink_timer;
    public float blink_Speed;
    bool isOpen_Eyes, isClose_Eyes;

    //����
    [Header("����")]
    public float breathe_value;
    
    //˵��
    [Header("˵��")]
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
        //�Ƕ�X
        model.Parameters[0].Value = look_pos.x;
        //�Ƕ�Y
        model.Parameters[1].Value = look_pos.y;
        //�Ƕ�Z
        //model.Parameters[2].Value = head_angle;

        //���շ���
        //model.Parameters[3].Value = ;
        //���ۿ���
        model.Parameters[4].Value = blink_OpenValue;
        //����΢Ц
        //model.Parameters[5].Value = ;
        //���ۿ���
        model.Parameters[6].Value = blink_OpenValue;
        //����΢Ц
        //model.Parameters[7].Value = ;

        //����X
        model.Parameters[8].Value = look_pos.x/30;
        //����Y
        model.Parameters[9].Value = look_pos.y/30;
        //��ü����
        //model.Parameters[10].Value = ;
        //��ü����
        //model.Parameters[11].Value = ;
        //�����
        //model.Parameters[12].Value = ;
        //�쿪��
        model.Parameters[13].Value = talk_value;
        //������תX
        model.Parameters[14].Value = look_pos.x/3;
        //������תY
        model.Parameters[15].Value = look_pos.y/3;
        //������תZ
        //model.Parameters[16].Value = ;
        //������תZ
        //model.Parameters[16].Value = ;
        //����
        model.Parameters[17].Value = breathe_value;
        //��� A
        model.Parameters[18].Value = breathe_value * 1.5f;
        //�ұ� B
        model.Parameters[19].Value = breathe_value * 1.5f;

        //�ز�ҡ��
        //model.Parameters[20].Value = ;
        //ͷ��ҡ�� ǰ
        //model.Parameters[21].Value = ;
        //ͷ��ҡ�� ��
        //model.Parameters[22].Value = ;
        //ͷ��ҡ�� ��
        //model.Parameters[23].Value = ;
        //���ӵ�ҡ��
        //model.Parameters[24].Value = ;
        //�������ҡ��
        //model.Parameters[25].Value = ;
        //��ȹ��ҡ��
        //model.Parameters[26].Value = ;
        //���ε�ҡ��
        //model.Parameters[27].Value = ;
        model.ForceUpdateNow();
    }

    //գ�۷���
    private void Blink()
    {
        if (blink_timer <= 0)
        {
            if (isClose_Eyes && !isOpen_Eyes)
            {
                //����
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
                //����
                blink_OpenValue -= Time.deltaTime * blink_Speed;
                if (blink_OpenValue <= 0) { isClose_Eyes = true; }
            }
        }
        else
        {
            blink_timer -= Time.deltaTime;
        }
    }
    //˵������
    private void Talk()
    {
        if (isTalking)
        {
            if (isClose_Talk && !isOpen_Talk)
            {
                //��
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
                //��
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
